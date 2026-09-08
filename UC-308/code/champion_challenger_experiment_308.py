"""
UC-308 — Champion/Challenger experiment orchestrator.

Deterministic state machine: draft → historical → walk_forward → shadow → paper
→ awaiting_approval → promoted/rejected/stopped/contained.

UC-308 owns evaluation and drift, and only **recommends** promotion; it never
auto-promotes or executes real orders. Paper trading is simulated via
deterministic engines with common execution assumptions.
"""

from __future__ import annotations

import hashlib
import json
import random
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Protocol, Sequence, Tuple, runtime_checkable

from cc_audit_308 import AuditChain
from cc_execution_308 import PaperExecutionEngine
from cc_metrics_308 import PromotionCriteria, StageMetricsCalculator, latest_stage_metrics
from cc_models_308 import (
    AuditNode,
    ExperimentConfig,
    ExperimentState,
    MarketEvent,
    ModelRegistration,
    OrderState,
    PortfolioSnapshot,
    Prediction,
    PromotionAction,
    PromotionRecommendation,
    StageMetrics,
)
from cc_predictors_308 import PredictorAdapter
from observability_308 import ObservabilityManager


_STATE_NUMERIC = {
    ExperimentState.DRAFT.value: 0,
    ExperimentState.HISTORICAL.value: 1,
    ExperimentState.WALK_FORWARD.value: 2,
    ExperimentState.SHADOW.value: 3,
    ExperimentState.PAPER.value: 4,
    ExperimentState.AWAITING_APPROVAL.value: 5,
    ExperimentState.PROMOTED.value: 6,
    ExperimentState.REJECTED.value: 7,
    ExperimentState.STOPPED.value: 8,
    ExperimentState.CONTAINED.value: 9,
}


@runtime_checkable
class AuthorityGuardAdapter(Protocol):
    def authorize_experiment_trade(self, request: Dict[str, Any]) -> Dict[str, Any]:
        ...


@runtime_checkable
class HITLApprovalAdapter(Protocol):
    def approve_experiment_promotion(self, request: Dict[str, Any]) -> Dict[str, Any]:
        ...


@runtime_checkable
class ShutdownAdapter(Protocol):
    def stop_experiment(
        self,
        experiment_id: str,
        trace_id: str,
        rollback_fn: Optional[Callable[[], Dict[str, Any]]],
    ) -> Dict[str, Any]:
        ...


@runtime_checkable
class PaperExecutionAdapter(Protocol):
    """Injectable paper-only boundary; UC-308 never discovers or auto-wires it."""

    def register_engine(
        self, experiment_id: str, model_id: str, version: str, engine: Any
    ) -> Dict[str, Any]:
        ...

    def execute(self, request: Dict[str, Any]) -> Dict[str, Any]:
        ...


class DefaultAuthorityGuard:
    """Safe default: challenger/shadow/paper only; real execution denied."""

    def authorize_experiment_trade(self, request: Dict[str, Any]) -> Dict[str, Any]:
        state = request.get("experiment_state", "")
        role = request.get("model_role", "")
        real_order = request.get("real_order", False)
        if real_order and role == "challenger" and state != "promoted":
            return {"allowed": False, "mode": "denied", "reason": "challenger real order denied before approved promotion"}
        return {"allowed": True, "mode": "paper_only", "reason": "paper execution authorized"}


class DefaultHITL:
    """Safe default: never auto-approves."""

    def approve_experiment_promotion(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return {"approved": False, "reason": "no HITL adapter configured"}


class DefaultShutdown:
    """No-op shutdown adapter that still returns an offline postmortem."""

    def stop_experiment(
        self,
        experiment_id: str,
        trace_id: str,
        rollback_fn: Optional[Callable[[], Dict[str, Any]]],
    ) -> Dict[str, Any]:
        rollback_result = rollback_fn() if rollback_fn else {"rolled_back": False}
        return {
            "shutdown_id": f"noop-{experiment_id}",
            "trace_id": trace_id,
            "state": "SAFE_STOPPED",
            "rollback_result": rollback_result,
            "reason": "no-op offline shutdown",
        }


class ChampionChallengerExperiment:
    """End-to-end deterministic champion/challenger experiment."""

    PAPER_STAGES = {
        ExperimentState.SHADOW.value,
        ExperimentState.PAPER.value,
        ExperimentState.AWAITING_APPROVAL.value,
        ExperimentState.PROMOTED.value,
    }

    def __init__(
        self,
        config: Optional[ExperimentConfig] = None,
        observability: Optional[ObservabilityManager] = None,
        authority_guard: Optional[AuthorityGuardAdapter] = None,
        hitl_adapter: Optional[HITLApprovalAdapter] = None,
        shutdown_adapter: Optional[ShutdownAdapter] = None,
        paper_execution_adapter: Optional[PaperExecutionAdapter] = None,
    ):
        self.config = config or ExperimentConfig()
        self.experiment_id = self.config.experiment_id or f"cce-{uuid.uuid4().hex[:12]}"
        self.state = ExperimentState.DRAFT.value
        self.observability = observability or ObservabilityManager(component="uc308_cc", pipeline="uc308_cc")
        self.authority = authority_guard or DefaultAuthorityGuard()
        self.hitl = hitl_adapter or DefaultHITL()
        self.shutdown = shutdown_adapter or DefaultShutdown()
        self.paper_execution_adapter = paper_execution_adapter or None

        self.champion_reg: Optional[ModelRegistration] = None
        self.challenger_reg: Optional[ModelRegistration] = None
        self.champion_predictor: Optional[PredictorAdapter] = None
        self.challenger_predictor: Optional[PredictorAdapter] = None

        self.champion_engine: Optional[PaperExecutionEngine] = None
        self.challenger_engine: Optional[PaperExecutionEngine] = None

        self.events: List[MarketEvent] = []
        self._event_ids: set = set()
        self.predictions: Dict[str, List[Prediction]] = {"champion": [], "challenger": []}
        self.outcomes: Dict[str, List[Dict[str, Any]]] = {"champion": [], "challenger": []}
        self.metrics_by_stage: Dict[str, StageMetrics] = {}
        self.recommendation: Optional[PromotionRecommendation] = None
        self.audit = AuditChain()
        self.last_source_ts: Optional[float] = None
        self._closed = False
        self._stage_sample_target = {
            ExperimentState.HISTORICAL.value: self.config.min_paired_samples,
            ExperimentState.WALK_FORWARD.value: self.config.walk_forward_samples,
            ExperimentState.SHADOW.value: self.config.shadow_samples,
            ExperimentState.PAPER.value: self.config.paper_samples,
        }
        self._stage_counts: Dict[str, int] = {s.value: 0 for s in ExperimentState}
        self._shutdown_postmortem: Optional[Dict[str, Any]] = None
        self._seen_event_ids: set = set()
        self._hitl_used_request_ids: set = set()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    def register_champion(
        self,
        model_id: str,
        version: str,
        predictor: PredictorAdapter,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ModelRegistration:
        self.champion_reg = ModelRegistration(
            model_id=model_id, version=version, role="champion", metadata=metadata or {}
        )
        self._bind_builtin_predictor(predictor, model_id, version)
        self.champion_predictor = predictor
        self.champion_engine = self._build_engine(self.champion_reg)
        if self.paper_execution_adapter is not None:
            self.paper_execution_adapter.register_engine(
                self.experiment_id, self.champion_reg.model_id, self.champion_reg.version, self.champion_engine
            )
        self.audit.append("register_champion", self.champion_reg.to_dict())
        return self.champion_reg

    def register_challenger(
        self,
        model_id: str,
        version: str,
        predictor: PredictorAdapter,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ModelRegistration:
        self.challenger_reg = ModelRegistration(
            model_id=model_id, version=version, role="challenger", metadata=metadata or {}
        )
        self._bind_builtin_predictor(predictor, model_id, version)
        self.challenger_predictor = predictor
        self.challenger_engine = self._build_engine(self.challenger_reg)
        if self.paper_execution_adapter is not None:
            self.paper_execution_adapter.register_engine(
                self.experiment_id, self.challenger_reg.model_id, self.challenger_reg.version, self.challenger_engine
            )
        self.audit.append("register_challenger", self.challenger_reg.to_dict())
        return self.challenger_reg

    @staticmethod
    def _bind_builtin_predictor(predictor: PredictorAdapter, model_id: str, version: str) -> None:
        """Bind only UC-308 demo predictors; external adapters own their identity.

        Mutating every injected predictor would hide a stale or malicious external
        model/version. Its emitted identity is instead checked during ingestion.
        """
        if predictor.__class__.__name__ in {"ChampionDemoPredictor", "ChallengerDemoPredictor"}:
            predictor.model_id = model_id
            predictor.version = version

    def _build_engine(self, reg: ModelRegistration) -> PaperExecutionEngine:
        return PaperExecutionEngine(
            model_id=reg.model_id,
            version=reg.version,
            initial_cash=self.config.initial_cash,
            fee_rate=self.config.fee_rate,
            base_latency_ms=self.config.base_latency_ms,
            slippage_model=self.config.slippage_model,
            max_position=self.config.max_position,
            max_exposure=self.config.max_exposure,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self, stage: str) -> Dict[str, Any]:
        if self.state != ExperimentState.DRAFT.value:
            return {"success": False, "reason": f"cannot start from state {self.state}"}
        if not self.champion_reg or not self.challenger_reg:
            return {"success": False, "reason": "both champion and challenger must be registered"}
        if not self.champion_predictor or not self.challenger_predictor:
            return {"success": False, "reason": "both predictors must be registered"}
        if stage not in {s.value for s in ExperimentState}:
            return {"success": False, "reason": f"invalid stage {stage}"}
        self.state = stage
        self.observability.gauge(
            "uc308_cc_experiment_state",
            _STATE_NUMERIC.get(self.state, -1),
            {"experiment_id": self.experiment_id},
        )
        self.audit.append("start_stage", {"stage": stage, "experiment_id": self.experiment_id})
        return {"success": True, "stage": stage}

    def transition(self, new_state: str, reason: str = "") -> Dict[str, Any]:
        allowed = self._allowed_transition(new_state)
        if not allowed["ok"]:
            return allowed
        old = self.state
        self.state = new_state
        self.observability.gauge(
            "uc308_cc_experiment_state",
            _STATE_NUMERIC.get(self.state, -1),
            {"experiment_id": self.experiment_id},
        )
        self.audit.append("state_transition", {
            "from": old,
            "to": new_state,
            "reason": reason,
            "experiment_id": self.experiment_id,
        })
        return {"success": True, "from": old, "to": new_state}

    def _allowed_transition(self, new_state: str) -> Dict[str, Any]:
        if new_state not in {s.value for s in ExperimentState}:
            return {"ok": False, "success": False, "reason": f"invalid state {new_state}"}
        # Prevent transitions out of terminal states.
        if self.state in {
            ExperimentState.PROMOTED.value,
            ExperimentState.REJECTED.value,
            ExperimentState.STOPPED.value,
            ExperimentState.CONTAINED.value,
        } and new_state != self.state:
            return {"ok": False, "success": False, "reason": f"terminal state {self.state} cannot transition"}
        return {"ok": True}

    # ------------------------------------------------------------------
    # Event ingestion
    # ------------------------------------------------------------------
    def ingest_event(self, event: MarketEvent) -> Dict[str, Any]:
        if self._closed:
            return {"success": False, "reason": "experiment stopped; new market events rejected"}
        ok, reason = event.validate(self.last_source_ts)
        if event.event_id in self._event_ids:
            ok, reason = False, "duplicate event_id"
        if not ok:
            self.audit.append("event_rejected", {"event_id": event.event_id, "reason": reason})
            self.observability.increment("uc308_cc_events_rejected_total", 1, {"reason": reason})
            return {"success": False, "reason": reason}

        self.last_source_ts = event.source_ts
        self.events.append(event)
        self._event_ids.add(event.event_id)
        self._stage_counts[self.state] = self._stage_counts.get(self.state, 0) + 1
        event_hash = event.event_hash()
        prediction_ts = time.time()
        correlation_id = f"{self.experiment_id}-{event.event_id}-{prediction_ts:.6f}"

        champion_pred = self.champion_predictor.predict(event, correlation_id, prediction_ts)
        challenger_pred = self.challenger_predictor.predict(event, correlation_id, prediction_ts)

        # Reject mismatched fan-out.
        if champion_pred.input_hash != event_hash or challenger_pred.input_hash != event_hash:
            reason = "prediction input_hash does not match event hash"
            self.audit.append("prediction_rejected", {"event_id": event.event_id, "reason": reason})
            return {"success": False, "reason": reason}
        if champion_pred.correlation_id != correlation_id or challenger_pred.correlation_id != correlation_id:
            reason = "predictor correlation_id mismatch"
            self.audit.append("prediction_rejected", {"event_id": event.event_id, "reason": reason})
            return {"success": False, "reason": reason}
        if champion_pred.prediction_ts != prediction_ts or challenger_pred.prediction_ts != prediction_ts:
            reason = "predictor timestamp mismatch"
            self.audit.append("prediction_rejected", {"event_id": event.event_id, "reason": reason})
            return {"success": False, "reason": reason}
        if (
            champion_pred.model_id != self.champion_reg.model_id
            or champion_pred.version != self.champion_reg.version
            or challenger_pred.model_id != self.challenger_reg.model_id
            or challenger_pred.version != self.challenger_reg.version
        ):
            reason = "prediction model/version does not match registration"
            self.audit.append("prediction_rejected", {"event_id": event.event_id, "reason": reason})
            return {"success": False, "reason": reason}

        self.predictions["champion"].append(champion_pred)
        self.predictions["challenger"].append(challenger_pred)
        self.outcomes["champion"].append({
            "event": event, "prediction": champion_pred, "order": None, "fills": [], "snapshot": None,
        })
        self.outcomes["challenger"].append({
            "event": event, "prediction": challenger_pred, "order": None, "fills": [], "snapshot": None,
        })

        self.audit.append("event_ingested", {
            "event_id": event.event_id,
            "event_hash": event_hash,
            "correlation_id": correlation_id,
            "prediction_ts": prediction_ts,
            "champion_prediction": champion_pred.to_dict(),
            "challenger_prediction": challenger_pred.to_dict(),
        })
        self.observability.increment("uc308_cc_events_ingested_total", 1, {"stage": self.state})

        # Paper execution only in shadow/paper/approval/promoted stages.
        if self.state in self.PAPER_STAGES:
            self._run_paper_execution(event, champion_pred, "champion")
            self._run_paper_execution(event, challenger_pred, "challenger")

        # Divergence / stale feed observability.
        spread = event.spread
        mid = event.mid
        if spread > mid * 0.05:
            self.observability.increment("uc308_cc_wide_spread_total", 1, {"symbol": event.symbol})

        return {
            "success": True,
            "event_id": event.event_id,
            "correlation_id": correlation_id,
            "stage": self.state,
        }

    def _run_paper_execution(self, event: MarketEvent, prediction: Prediction, role: str) -> None:
        engine = self.champion_engine if role == "champion" else self.challenger_engine
        if engine is None:
            return
        auth = self.authority.authorize_experiment_trade({
            "experiment_id": self.experiment_id,
            "experiment_state": self.state,
            "model_id": prediction.model_id,
            "model_version": prediction.version,
            "model_role": role,
            "event_id": event.event_id,
            "real_order": False,
        })
        if not auth.get("allowed", False):
            self.audit.append("paper_execution_denied", {
                "role": role,
                "event_id": event.event_id,
                "reason": auth.get("reason", "authority denied"),
            })
            self.observability.increment("uc308_cc_authority_denials_total", 1, {"role": role})
            return

        if self.paper_execution_adapter is not None:
            response = self.paper_execution_adapter.execute({
                "experiment_id": self.experiment_id,
                "model_id": prediction.model_id,
                "version": prediction.version,
                "model_role": role,
                "event_id": event.event_id,
                "market_event": event,
                "prediction": prediction,
                "real_order": False,
            })
            if not response.get("success", False):
                self.audit.append("paper_execution_denied", {
                    "role": role,
                    "event_id": event.event_id,
                    "reason": response.get("reason", "adapter denied"),
                })
                self.observability.increment("uc308_cc_authority_denials_total", 1, {"role": role})
                return
            result = response
        else:
            result = engine.process_event(event, prediction)
        self.outcomes[role][-1].update({
            "order": result.get("order"),
            "fills": result.get("fills"),
            "snapshot": result.get("snapshot"),
        })
        self.audit.append("paper_outcome", {
            "role": role,
            "event_id": event.event_id,
            "order": result.get("order"),
            "fills": result.get("fills"),
            "snapshot": result.get("snapshot"),
        })
        snap = result.get("snapshot")
        if snap:
            self.observability.gauge("uc308_cc_pnl", snap.get("total_pnl", 0.0), {"role": role})
            self.observability.gauge("uc308_cc_exposure", snap.get("exposure", 0.0), {"role": role})
            self.observability.gauge("uc308_cc_drawdown", snap.get("max_drawdown", 0.0), {"role": role})
            if snap.get("max_drawdown", 0.0) > self.config.max_drawdown:
                self.observability.increment("uc308_cc_drawdown_violation_total", 1, {"role": role})

    # ------------------------------------------------------------------
    # Metrics and stage gate
    # ------------------------------------------------------------------
    def compute_metrics(self) -> Dict[str, StageMetrics]:
        calc = StageMetricsCalculator()
        metrics = {}
        for role in ("champion", "challenger"):
            metrics[role] = calc.compute(self.state, self.outcomes[role])
            labels = {"role": role, "stage": self.state, "experiment_id": self.experiment_id}
            self.observability.gauge("uc308_cc_bid_mae", metrics[role].bid_mae, labels)
            self.observability.gauge("uc308_cc_ask_mae", metrics[role].ask_mae, labels)
            self.observability.gauge("uc308_cc_pnl", metrics[role].total_pnl, labels)
            self.observability.gauge("uc308_cc_exposure", metrics[role].avg_exposure, labels)
            self.observability.gauge("uc308_cc_drawdown", metrics[role].max_drawdown, labels)
        self.metrics_by_stage[self.state] = metrics["challenger"]
        self.observability.gauge(
            "uc308_cc_experiment_state",
            _STATE_NUMERIC.get(self.state, -1),
            {"experiment_id": self.experiment_id},
        )
        return metrics

    def evaluate_stage_gate(self) -> Dict[str, Any]:
        metrics = self.compute_metrics()
        champ = metrics["champion"]
        chall = metrics["challenger"]

        # Risk containment gate.
        for role, m in metrics.items():
            if m.max_drawdown > self.config.max_drawdown:
                self.transition(ExperimentState.CONTAINED.value, f"{role} max_drawdown exceeded")
                return {"success": False, "reason": f"{role} max_drawdown {m.max_drawdown} > {self.config.max_drawdown}"}
            if m.avg_exposure > self.config.max_exposure:
                self.transition(ExperimentState.CONTAINED.value, f"{role} avg_exposure exceeded")
                return {"success": False, "reason": f"{role} avg_exposure {m.avg_exposure} > {self.config.max_exposure}"}

        current_count = self._stage_counts.get(self.state, 0)
        target = self._stage_sample_target.get(self.state, 1)
        if current_count < target:
            return {
                "success": True,
                "stage": self.state,
                "samples": current_count,
                "target": target,
                "gate": "insufficient_samples",
            }

        if self.state == ExperimentState.PAPER.value:
            # Compute paired PnL differences per event for statistical test.
            diffs = self._paired_pnl_differences()
            criteria = PromotionCriteria(self.config)
            assessment = criteria.evaluate(champ, chall, paired_pnl_diff=diffs)
            if assessment.get("decision") == "promote":
                self.transition(ExperimentState.AWAITING_APPROVAL.value, "stage gate passed")
                return {
                    "success": True,
                    "stage": self.state,
                    "gate": "ready_for_recommendation",
                    "assessment": assessment,
                }
            elif assessment.get("decision") == "reject":
                self.transition(ExperimentState.REJECTED.value, "challenger inferior")
                return {"success": False, "reason": "challenger rejected", "assessment": assessment}
            else:
                return {"success": True, "stage": self.state, "gate": "continue", "assessment": assessment}

        # Advance to next stage.
        next_stage = self._next_stage(self.state)
        if next_stage:
            return self.transition(next_stage, "stage samples reached")
        return {"success": True, "stage": self.state, "gate": "no_advance"}

    def _next_stage(self, current: str) -> Optional[str]:
        mapping = {
            ExperimentState.HISTORICAL.value: ExperimentState.WALK_FORWARD.value,
            ExperimentState.WALK_FORWARD.value: ExperimentState.SHADOW.value,
            ExperimentState.SHADOW.value: ExperimentState.PAPER.value,
        }
        return mapping.get(current)

    def _paired_pnl_differences(self) -> List[float]:
        champ = self.outcomes["champion"]
        chall = self.outcomes["challenger"]
        n = min(len(champ), len(chall))
        diffs: List[float] = []
        for i in range(n):
            cp = (champ[i].get("snapshot") or {}).get("total_pnl", 0.0)
            cc = (chall[i].get("snapshot") or {}).get("total_pnl", 0.0)
            diffs.append(cc - cp)
        return diffs

    # ------------------------------------------------------------------
    # Recommendation and approval
    # ------------------------------------------------------------------
    def recommend_promotion(self) -> PromotionRecommendation:
        metrics = self.compute_metrics()
        champ = metrics["champion"]
        chall = metrics["challenger"]
        diffs = self._paired_pnl_differences()
        criteria = PromotionCriteria(self.config)
        assessment = criteria.evaluate(champ, chall, paired_pnl_diff=diffs)

        action = PromotionAction.CONTINUE.value
        reason = assessment.get("reason", "no assessment")
        if assessment.get("eligible"):
            if assessment["decision"] == "promote":
                action = PromotionAction.PROMOTE.value
            elif assessment["decision"] == "reject":
                action = PromotionAction.REJECT.value

        report_payload = {
            "experiment_id": self.experiment_id,
            "state": self.state,
            "champion_version": self.champion_reg.version if self.champion_reg else "",
            "challenger_version": self.challenger_reg.version if self.challenger_reg else "",
            "champion_metrics": champ.to_dict(),
            "challenger_metrics": chall.to_dict(),
            "assessment": assessment,
        }
        report_hash = hashlib.sha256(
            json.dumps(report_payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest()

        rec = PromotionRecommendation(
            experiment_id=self.experiment_id,
            report_hash=report_hash,
            state=self.state,
            recommended_action=action,
            reason=reason,
            champion_version=self.champion_reg.version if self.champion_reg else "",
            challenger_version=self.challenger_reg.version if self.challenger_reg else "",
            metrics_summary={
                "champion": champ.to_dict(),
                "challenger": chall.to_dict(),
            },
            confidence_intervals=assessment.get("ci", {}),
            timestamp=time.time(),
        )
        self.recommendation = rec
        self.audit.append("recommendation", rec.to_dict())
        self.observability.increment("uc308_cc_recommendations_total", 1, {"action": action})
        return rec

    def approve_promotion(
        self,
        report_hash: str,
        reviewer_id: str,
        request_id: str,
        ttl_seconds: float = 3600.0,
        timestamp: Optional[float] = None,
    ) -> Dict[str, Any]:
        if self.state != ExperimentState.AWAITING_APPROVAL.value:
            return {"success": False, "reason": f"experiment not awaiting approval (state={self.state})"}
        if not self.recommendation:
            return {"success": False, "reason": "no recommendation exists"}
        if not reviewer_id or not reviewer_id.strip():
            return {"success": False, "reason": "reviewer_id required; cannot auto-approve"}
        if ttl_seconds <= 0:
            return {"success": False, "reason": "ttl_seconds must be > 0"}
        if request_id in self._hitl_used_request_ids:
            return {"success": False, "reason": "request_id already used (anti-replay)"}
        self._hitl_used_request_ids.add(request_id)

        now = time.time()
        ts = timestamp if timestamp is not None else now
        if ts > now + 60.0:
            return {"success": False, "reason": "timestamp unreasonably far in the future"}
        if (now - ts) > ttl_seconds:
            return {"success": False, "reason": "approval request expired (TTL)"}
        if self.recommendation.report_hash != report_hash:
            return {"success": False, "reason": "report_hash mismatch"}
        if self.recommendation.recommended_action != PromotionAction.PROMOTE.value:
            return {"success": False, "reason": "recommendation action does not authorize promotion"}

        approval = self.hitl.approve_experiment_promotion({
            "experiment_id": self.experiment_id,
            "report_hash": report_hash,
            "champion_version": self.champion_reg.version if self.champion_reg else "",
            "challenger_version": self.challenger_reg.version if self.challenger_reg else "",
            "reviewer_id": reviewer_id,
            "request_id": request_id,
            "ttl_seconds": ttl_seconds,
            "timestamp": ts,
        })
        if not approval.get("approved", False):
            return {"success": False, "reason": approval.get("reason", "HITL denied")}

        self.recommendation.approved = True
        self.recommendation.approval_info = approval
        self.transition(ExperimentState.PROMOTED.value, "human approval granted")
        self.audit.append("approval", {
            "experiment_id": self.experiment_id,
            "report_hash": report_hash,
            "reviewer_id": reviewer_id,
            "request_id": request_id,
            "timestamp": ts,
        })
        self.observability.increment("uc308_cc_promotions_approved_total", 1, {"experiment_id": self.experiment_id})
        return {"success": True, "state": ExperimentState.PROMOTED.value}

    # ------------------------------------------------------------------
    # Safe shutdown
    # ------------------------------------------------------------------
    def shutdown_experiment(self, reason: str = "manual") -> Dict[str, Any]:
        self._closed = True
        trace_id = f"{self.experiment_id}-shutdown-{uuid.uuid4().hex[:8]}"

        def rollback() -> Dict[str, Any]:
            # Cancel pending paper orders and roll back simulated promotion state.
            canceled_champ = []
            if self.champion_engine:
                canceled_champ = [o.to_dict() for o in self.champion_engine.cancel_all_orders()]
            canceled_chall = []
            if self.challenger_engine:
                canceled_chall = [o.to_dict() for o in self.challenger_engine.cancel_all_orders()]
            rolled_state = self.state
            if self.state == ExperimentState.PROMOTED.value:
                self.state = ExperimentState.STOPPED.value
            return {
                "canceled_orders_champion": len(canceled_champ),
                "canceled_orders_challenger": len(canceled_chall),
                "simulated_promotion_rolled_back": rolled_state == ExperimentState.PROMOTED.value,
            }

        shutdown_result = self.shutdown.stop_experiment(self.experiment_id, trace_id, rollback)
        postmortem = shutdown_result.to_dict() if hasattr(shutdown_result, "to_dict") else shutdown_result
        self._shutdown_postmortem = postmortem
        final_state = postmortem.get("state", "STOPPED")
        if final_state == "CONTAINED":
            self.state = ExperimentState.CONTAINED.value
        else:
            self.state = ExperimentState.STOPPED.value

        reconciliation = {
            "experiment_id": self.experiment_id,
            "trace_id": trace_id,
            "final_state": self.state,
            "events_ingested": len(self.events),
            "predictions_champion": len(self.predictions["champion"]),
            "predictions_challenger": len(self.predictions["challenger"]),
            "filled_orders_champion": len(self.champion_engine.filled_orders) if self.champion_engine else 0,
            "filled_orders_challenger": len(self.challenger_engine.filled_orders) if self.challenger_engine else 0,
            "cash_champion": self.champion_engine.cash if self.champion_engine else self.config.initial_cash,
            "cash_challenger": self.challenger_engine.cash if self.challenger_engine else self.config.initial_cash,
            "position_champion": self.champion_engine.position if self.champion_engine else 0.0,
            "position_challenger": self.challenger_engine.position if self.challenger_engine else 0.0,
            "audit_chain_valid": self.audit.verify_chain(),
        }
        self.audit.append("shutdown_reconciliation", reconciliation)
        self.observability.increment("uc308_cc_shutdowns_total", 1, {"reason": reason, "final_state": self.state})
        return {
            "success": True,
            "experiment_id": self.experiment_id,
            "final_state": self.state,
            "trace_id": trace_id,
            "postmortem": postmortem,
            "reconciliation": reconciliation,
        }

    # ------------------------------------------------------------------
    # Status / helpers
    # ------------------------------------------------------------------
    def status(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "state": self.state,
            "samples_in_stage": self._stage_counts.get(self.state, 0),
            "total_events": len(self.events),
            "total_predictions": {
                "champion": len(self.predictions["champion"]),
                "challenger": len(self.predictions["challenger"]),
            },
            "champion_version": self.champion_reg.version if self.champion_reg else None,
            "challenger_version": self.challenger_reg.version if self.challenger_reg else None,
            "closed": self._closed,
            "audit_chain_valid": self.audit.verify_chain(),
            "latest_audit_hash": self.audit.last_hash,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "config": self.config.to_dict(),
            "state": self.state,
            "champion": self.champion_reg.to_dict() if self.champion_reg else None,
            "challenger": self.challenger_reg.to_dict() if self.challenger_reg else None,
            "status": self.status(),
            "recommendation": self.recommendation.to_dict() if self.recommendation else None,
            "metrics_by_stage": {k: v.to_dict() for k, v in self.metrics_by_stage.items()},
        }


class ChampionChallengerManager:
    """In-memory registry of experiments for the API."""

    def __init__(self) -> None:
        self.experiments: Dict[str, ChampionChallengerExperiment] = {}

    def create(
        self,
        config: Optional[ExperimentConfig] = None,
        experiment_id: Optional[str] = None,
    ) -> ChampionChallengerExperiment:
        cfg = config or ExperimentConfig()
        if experiment_id:
            cfg.experiment_id = experiment_id
        exp = ChampionChallengerExperiment(config=cfg)
        self.experiments[exp.experiment_id] = exp
        return exp

    def get(self, experiment_id: str) -> Optional[ChampionChallengerExperiment]:
        return self.experiments.get(experiment_id)

    def list_experiments(self) -> List[Dict[str, Any]]:
        return [e.status() for e in self.experiments.values()]

    def reset(self) -> None:
        self.experiments.clear()


# ------------------------------------------------------------------
# Deterministic market event generator for demos/tests.
# ------------------------------------------------------------------
def generate_market_events(
    symbol: str = "DEMO",
    n: int = 100,
    start_ts: float = 1_700_000_000.0,
    start_bid: float = 150.0,
    start_ask: float = 150.05,
    seed: int = 42,
) -> List[MarketEvent]:
    """Generate deterministic canonical market events with reference future prices."""
    rng = random.Random(seed)
    events: List[MarketEvent] = []
    bid = start_bid
    ask = start_ask
    for i in range(n):
        ts = start_ts + i * 1.0
        # Random walk with small drift.
        change = rng.gauss(0.0, 0.02)
        bid = max(1.0, round(bid + change, 4))
        ask = max(bid + 0.01, round(ask + change + rng.uniform(0.005, 0.015), 4))
        bid_size = max(1.0, round(rng.gauss(500.0, 100.0), 2))
        ask_size = max(1.0, round(rng.gauss(500.0, 100.0), 2))
        # Reference prices are a slightly advanced version of the same walk.
        ref_bid = max(1.0, round(bid + rng.gauss(0.0, 0.005), 4))
        ref_ask = max(ref_bid + 0.01, round(ask + rng.gauss(0.0, 0.005), 4))
        events.append(
            MarketEvent(
                event_id=f"{symbol}-{i:06d}",
                source_ts=ts,
                receive_ts=ts + rng.uniform(0.0, 0.05),
                symbol=symbol,
                bid=bid,
                ask=ask,
                bid_size=bid_size,
                ask_size=ask_size,
                reference_bid=ref_bid,
                reference_ask=ref_ask,
            )
        )
    return events
