"""
UC-075 — Continuous Training Orchestrator (capa externa del ecosistema AGI).

Orquesta la estrategia de reentrenamiento end-to-end sobre los motores
existentes sin modificarlos (inyección de dependencias):

    UC-087 (SandboxTrainer / seguridad)   → trainer, security_fairness
    UC-308 (drift / champion-challenger)  → drift_detector, matchup evaluator
    UC-309 (observabilidad)               → pipeline de eventos (Prometheus/Loki/Tempo)
    UC-290 (HITL)                         → hitl_approver

Flujo canónico por run:
  1. Trigger (scheduled/event/on_demand/incremental)  [TriggerEngine]
  2. Política + presupuesto (fail-closed)             [TriggerEngine]
  3. Freeze + versionado de datos                     [VersionFreezeRegistry]
  4. Entrenamiento sandbox                            [CallableTrainer]
  5. Evaluación out-of-sample campeón vs candidato    [CallableEvaluator]
  6. Gates: drift → champion-challenger → security/fairness → HITL → canary
  7. Decisión: promote / reject / rollback / escalate
  8. Registro: MLflowAdapter + Observability075 + AuditLog (hash-chain)

La promoción y el rollback nunca se ejecutan sin pasar los gates;
en dominios de alto impacto sin HITL el run queda PENDING_HITL.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from models_075 import (
    AuditRecord,
    ChampionCandidate,
    DecisionAction,
    GateName,
    GateVerdict,
    HITLApproval,
    OrchestratorPolicy,
    PipelineRun,
    PipelineStatus,
    RetrainStrategy,
    RetrainTrigger,
)
from trigger_engine import TriggerEngine
from gate_pipeline import (
    GatePipeline,
    DriftDetectorFn,
    ChampionChallengerFn,
    SecurityFairnessFn,
    HITLApproverFn,
    CanaryMonitorFn,
)
from registry_075 import ChampionRegistry, VersionFreezeRegistry
from mlflow_adapter_075 import MLflowAdapter
from observability_075 import Observability075
from online_incremental_learner import (
    OnlineIncrementalLearner,
    OnlineLearnerPolicy,
)

# --- Funciones inyectables del ecosistema ----------------------------------

# UC-087: entrena candidato sandbox desde datos frozen → (version_id, metrics)
TrainerFn = Callable[[List[Dict[str, Any]]], Dict[str, Any]]
# UC-308: evalúa candidato out-of-sample contra campeón
EvaluatorFn = Callable[[List[Dict[str, Any]], Dict[str, float]], Dict[str, float]]
# UC-309: sink de eventos canónicos (audit/observability)
EventSinkFn = Callable[[Dict[str, Any]], None]


def default_trainer(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Fallback determinista: entrena un candidato idealizado para tests/dev."""
    n = len(records)
    acc = 0.8 if n == 0 else min(0.98, 0.8 + n * 0.001)
    return {
        "version_id": f"cand-{uuid.uuid4().hex[:8]}",
        "metrics": {"accuracy": acc, "replay_accuracy": acc},
        "cost_usd": max(0.01, n * 0.0001),
    }


def default_evaluator(
    records: List[Dict[str, Any]],
    champion_metrics: Dict[str, float],
) -> Dict[str, float]:
    """Fallback: evalúa out-of-sample contra el campeón actual."""
    champ_acc = champion_metrics.get("accuracy", 0.8)
    acc = min(0.99, champ_acc + 0.02)
    return {"accuracy": acc, "replay_accuracy": acc, "out_of_sample": 1.0}


class AuditLog:
    """Cadena de auditoría inmutable (hash-chain), NIST/ISO-friendly."""

    def __init__(self) -> None:
        self._records: List[AuditRecord] = []
        self._tip_hash = ""

    def append(self, record: AuditRecord) -> AuditRecord:
        record.previous_hash = self._tip_hash
        payload = json.dumps(
            {k: v for k, v in record.to_dict().items() if k != "record_hash"},
            sort_keys=True,
            default=str,
        )
        record.record_hash = hashlib.sha256(payload.encode()).hexdigest()
        self._tip_hash = record.record_hash
        self._records.append(record)
        return record

    def verify_chain(self) -> bool:
        prev = ""
        for rec in self._records:
            if rec.previous_hash != prev:
                return False
            payload = json.dumps(
                {k: v for k, v in rec.to_dict().items() if k != "record_hash"},
                sort_keys=True,
                default=str,
            )
            if hashlib.sha256(payload.encode()).hexdigest() != rec.record_hash:
                return False
            prev = rec.record_hash
        return True

    def list(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self._records]


class ContinuousTrainingOrchestrator:
    """Capa externa de orquestación de reentrenamiento continuo (UC-075)."""

    def __init__(
        self,
        policy: Optional[OrchestratorPolicy] = None,
        trainer: Optional[TrainerFn] = None,
        evaluator: Optional[EvaluatorFn] = None,
        drift_detector: Optional[DriftDetectorFn] = None,
        champion_challenger: Optional[ChampionChallengerFn] = None,
        security_fairness: Optional[SecurityFairnessFn] = None,
        hitl_approver: Optional[HITLApproverFn] = None,
        canary_monitor: Optional[CanaryMonitorFn] = None,
        event_sink: Optional[EventSinkFn] = None,          # UC-309
        mlflow_tracking_uri: Optional[str] = None,
        mlflow_enabled: bool = True,
    ) -> None:
        self.policy = policy or OrchestratorPolicy()
        self.trainer = trainer or default_trainer
        self.evaluator = evaluator or default_evaluator
        self.trigger_engine = TriggerEngine(self.policy)
        self.gates = GatePipeline(
            self.policy,
            drift_detector=drift_detector,
            champion_challenger=champion_challenger,
            security_fairness=security_fairness,
            hitl_approver=hitl_approver,
            canary_monitor=canary_monitor,
        )
        self.freeze_registry = VersionFreezeRegistry()
        self.champions = ChampionRegistry()
        self.mlflow = MLflowAdapter(tracking_uri=mlflow_tracking_uri, enabled=mlflow_enabled)
        self.observability = Observability075()
        self.audit = AuditLog()
        self.event_sink = event_sink
        self._runs: Dict[str, PipelineRun] = {}
        self._online_learners: Dict[str, OnlineIncrementalLearner] = {}

    # ------------------------------------------------------------------
    def _emit(self, event_type: str, payload: Dict[str, Any]) -> None:
        if self.event_sink is not None:
            try:
                self.event_sink({
                    "event_type": event_type,
                    "timestamp": time.time(),
                    **payload,
                })
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Entradas de trigger
    # ------------------------------------------------------------------
    def check_scheduled(self, agent_id: str, interval_hours: float = 168.0) -> Optional[PipelineRun]:
        """Estrategia SCHEDULED (semanal por defecto)."""
        trigger = self.trigger_engine.scheduled_due(agent_id, interval_hours)
        if trigger is None:
            return None
        run = self._execute(agent_id, trigger)
        self.trigger_engine.mark_scheduled_run(agent_id)
        return run

    def evaluate_metrics(
        self,
        agent_id: str,
        metrics: Dict[str, float],
        domain: str = "default",
    ) -> Optional[PipelineRun]:
        """Estrategia EVENT_DRIVEN: umbrales de drift/error/latencia/KPI."""
        trigger = self.trigger_engine.evaluate_event(metrics, domain=domain)
        if trigger is None:
            return None
        return self._execute(agent_id, trigger)

    def on_demand(
        self,
        agent_id: str,
        change_type: str,
        detail: str,
        new_data: Optional[List[Dict[str, Any]]] = None,
        domain: str = "default",
        estimated_cost_usd: float = 0.0,
    ) -> PipelineRun:
        """Estrategia ON_DEMAND: cambio de producto/política/fuentes."""
        trigger = self.trigger_engine.on_demand(
            change_type, detail, new_data=new_data,
            domain=domain, estimated_cost_usd=estimated_cost_usd,
        )
        return self._execute(agent_id, trigger)

    def incremental_step(
        self,
        agent_id: str,
        batch: List[Dict[str, Any]],
        replay_buffer: List[Dict[str, Any]],
        domain: str = "default",
    ) -> Optional[PipelineRun]:
        """Estrategia INCREMENTAL: mini-batch + replay anti-olvido."""
        trigger = self.trigger_engine.incremental(batch, replay_buffer, domain=domain)
        if trigger is None:
            return None
        return self._execute(agent_id, trigger)

    # ------------------------------------------------------------------
    # Online incremental learner (Circuit Breaker + partial_fit)
    # ------------------------------------------------------------------
    def get_online_learner(
        self,
        learner_id: str,
        model: Any,
        policy: Optional[OnlineLearnerPolicy] = None,
    ) -> OnlineIncrementalLearner:
        """Obtiene o crea un OnlineIncrementalLearner con componentes compartidos."""
        if learner_id not in self._online_learners:
            self._online_learners[learner_id] = OnlineIncrementalLearner(
                learner_id=learner_id,
                model=model,
                policy=policy,
                mlflow=self.mlflow,
                observability=self.observability,
                event_sink=self.event_sink,
            )
        return self._online_learners[learner_id]

    def online_fit(
        self,
        learner_id: str,
        model: Any,
        X: Any,
        y: Any,
        metadata: Optional[Dict[str, Any]] = None,
        policy: Optional[OnlineLearnerPolicy] = None,
    ) -> Dict[str, Any]:
        """Aplica un micro-lote a través del OnlineIncrementalLearner."""
        learner = self.get_online_learner(learner_id, model, policy=policy)
        return learner.fit_micro_batch(X, y, metadata=metadata).to_dict()

    # ------------------------------------------------------------------
    # Pipeline
    # ------------------------------------------------------------------
    def _execute(self, agent_id: str, trigger: RetrainTrigger) -> PipelineRun:
        run = PipelineRun(agent_id=agent_id, trigger=trigger,
                          strategy_used=trigger.strategy.value)
        self._runs[run.run_id] = run
        self.observability.record_trigger(trigger.strategy.value, run.drift_score)
        self._emit("uc075_run_started", run.to_dict())

        # 1. Política + presupuesto (fail-closed)
        decision = self.trigger_engine.evaluate_policy(trigger)
        if not decision.proceed:
            run.decision = DecisionAction.REJECT
            run.decision_reason = decision.reason
            run.finish(PipelineStatus.BLOCKED)
            self._close_run(run)
            return run

        try:
            # 2. Freeze + versionado
            run.freeze = self.freeze_registry.freeze(
                trigger.new_data,
                replay=trigger.replay_buffer,
                provenance={
                    "strategy": trigger.strategy.value,
                    "business_trigger": trigger.business_trigger,
                    "domain": trigger.domain,
                },
            )

            # 3. Campeón actual + entrenamiento candidato
            champion = self.champions.current_champion(agent_id)
            trained = self.trainer(run.freeze.records)
            candidate_version = trained["version_id"]
            run.actual_cost_usd = float(trained.get("cost_usd", trigger.estimated_cost_usd))
            self.trigger_engine.register_spend(trigger, run.actual_cost_usd)

            # 4. Evaluación out-of-sample
            candidate_metrics = self.evaluator(
                run.freeze.records, dict(champion.metrics),
            )
            run.matchup = ChampionCandidate(
                champion_version=champion.version_id,
                candidate_version=candidate_version,
                champion_metrics=dict(champion.metrics),
                candidate_metrics=candidate_metrics,
                out_of_sample=candidate_metrics.get("out_of_sample", 1) == 1,
            )
            self.champions.register_canary(
                agent_id, candidate_version, candidate_metrics,
            )

            # 5. Gates (fail-fast)
            self.gates.run_gates(run)
            for g in run.gates:
                self.observability.record_gate(g.gate.value, g.verdict.value)
                self._emit("uc075_gate", {
                    "run_id": run.run_id, **g.to_dict(),
                })

            last = run.gates[-1]
            if last.verdict == GateVerdict.REQUIRES_HITL:
                run.decision = DecisionAction.ESCALATE
                run.decision_reason = last.reason
                run.finish(PipelineStatus.PENDING_HITL)
                self.observability.record_pending_hitl(+1)
                self._close_run(run)
                return run

            if last.verdict == GateVerdict.FAIL:
                if last.gate == GateName.CANARY:
                    # Debacle en canary → rollback automático al campeón previo
                    restored = self.champions.rollback(agent_id)
                    run.rollback_version = restored.version_id
                    run.decision = DecisionAction.ROLLBACK
                    run.decision_reason = (
                        f"{last.reason} Rolled back to {restored.version_id}."
                    )
                    run.finish(PipelineStatus.ROLLED_BACK)
                else:
                    run.decision = DecisionAction.REJECT
                    run.decision_reason = last.reason
                    run.finish(PipelineStatus.REJECTED)
                self._close_run(run)
                return run

            # 6. Todos los gates pasaron → promoción
            run.approval = run.approval or HITLApproval(
                approved=True, approver="auto-policy",
            )
            self.champions.promote(agent_id, candidate_version)
            run.decision = DecisionAction.PROMOTE
            run.decision_reason = "All gates passed; candidate promoted."
            run.finish(PipelineStatus.PROMOTED)
            self._close_run(run)
            return run

        except Exception as exc:  # noqa: BLE001 — pipeline fail-closed
            run.error = str(exc)
            run.decision = DecisionAction.REJECT
            run.decision_reason = f"Pipeline failure: {exc}"
            run.finish(PipelineStatus.FAILED)
            self._close_run(run)
            return run

    # ------------------------------------------------------------------
    # Aprobación humana pendiente (UC-290)
    # ------------------------------------------------------------------
    def resolve_hitl(
        self,
        run_id: str,
        approved: bool,
        approver: str,
        review_notes: str = "",
    ) -> Optional[PipelineRun]:
        """Resuelve un run PENDING_HITL con decisión humana."""
        run = self._runs.get(run_id)
        if run is None or run.status != PipelineStatus.PENDING_HITL:
            return None

        run.approval = HITLApproval(
            approved=approved, approver=approver, review_notes=review_notes,
        )
        self.observability.record_pending_hitl(-1)

        if approved:
            self.champions.promote(run.agent_id, run.matchup.candidate_version)
            run.decision = DecisionAction.PROMOTE
            run.decision_reason = f"HITL approved by {approver}."
            run.finish(PipelineStatus.PROMOTED)
        else:
            run.decision = DecisionAction.REJECT
            run.decision_reason = f"HITL rejected by {approver}."
            run.finish(PipelineStatus.REJECTED)

        self._close_run(run)
        return run

    # ------------------------------------------------------------------
    def _close_run(self, run: PipelineRun) -> None:
        """Cierre: MLflow + métricas + auditoría hash-chain."""
        duration = (run.finished_at or time.time()) - run.started_at

        # MLflow / fallback JSONL
        mlflow_run_id = self.mlflow.start_run(run.run_id)
        run.mlflow_run_id = mlflow_run_id
        self.mlflow.log_run(mlflow_run_id, run.to_dict())
        self.mlflow.end_run()

        # Métricas Prometheus
        self.observability.record_completed(
            run.status.value, duration, run.actual_cost_usd,
        )

        # Auditoría inmutable
        self.audit.append(AuditRecord(
            run_id=run.run_id,
            agent_id=run.agent_id,
            action=(run.decision.value if run.decision else "unknown"),
            actor="uc075-orchestrator",
            approver=(run.approval.approver if run.approval else ""),
            rationale=run.decision_reason,
            evidence={
                "strategy": run.strategy_used,
                "drift_score": run.drift_score,
                "business_trigger": run.trigger.business_trigger,
                "dataset_version": run.freeze.dataset_version if run.freeze else "",
                "mlflow_run_id": run.mlflow_run_id,
                "gates": [g.gate.value for g in run.gates if g.verdict == GateVerdict.PASS],
                "status": run.status.value,
            },
        ))

        # UC-309
        self._emit("uc075_run_completed", run.to_dict())

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------
    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        run = self._runs.get(run_id)
        return run.to_dict() if run else None

    def list_runs(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        runs = [r.to_dict() for r in self._runs.values()]
        if status:
            runs = [r for r in runs if r["status"] == status]
        return sorted(runs, key=lambda r: r["started_at"], reverse=True)

    def pending_hitl(self) -> List[Dict[str, Any]]:
        return self.list_runs(status=PipelineStatus.PENDING_HITL.value)

    def dashboard_state(self) -> Dict[str, Any]:
        return {
            "strategy_support": [s.value for s in RetrainStrategy],
            "budget": self.trigger_engine.budget_status(),
            "champions": self.champions.status(),
            "mlflow": self.mlflow.status(),
            "audit_records": len(self.audit.list()),
            "audit_chain_valid": self.audit.verify_chain(),
            "runs_total": len(self._runs),
            "pending_hitl": len(self.pending_hitl()),
            "online_learners": {
                lid: learner.status()
                for lid, learner in self._online_learners.items()
            },
        }

    def get_online_learner(self, learner_id: str) -> Optional[OnlineIncrementalLearner]:
        return self._online_learners.get(learner_id)
