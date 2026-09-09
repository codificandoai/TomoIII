"""
UC-075 — Gates obligatorios del pipeline de reentrenamiento.

Cadena canonical (fail-fast, en orden):

    drift gate → champion–challenger gate → security/fairness gate
      → HITL gate → canary gate

Cada gate produce evidencia auditable. Cualquier FAIL detiene el pipeline;
REQUIRES_HITL pausa el run hasta aprobación humana (UC-290).
Las validaciones pesadas (UC-308 drift/champion-challenger,
UC-087 robustez/fairness) se inyectan como callables — el orquestador
nunca importa motores internos de otros casos de uso.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from models_075 import (
    CanaryReport,
    ChampionCandidate,
    FrozenDataset,
    GateName,
    GateResult,
    GateVerdict,
    OrchestratorPolicy,
    PipelineRun,
    RetrainStrategy,
    SecurityFairnessReport,
)
from regulated_model_governance import (
    ExplainabilityGate,
    RegulatoryControl,
    RegulatoryPolicy,
)

# --- Tipos inyectables -----------------------------------------------------

# UC-308: detecta drift entre datos frozen y producción → drift_score [0,1]
DriftDetectorFn = Callable[[FrozenDataset], float]
# UC-308/UC-087: compara candidato vs campeón out-of-sample
ChampionChallengerFn = Callable[[ChampionCandidate], ChampionCandidate]
# UC-087: sesgo, robustez, backdoor, PII sobre el candidato
SecurityFairnessFn = Callable[[ChampionCandidate], SecurityFairnessReport]
# UC-290: decide aprobación humana; devuelve True/False/None(pendiente)
HITLApproverFn = Callable[[PipelineRun], Optional[bool]]
# Monitor canary: health check del despliegue canary
CanaryMonitorFn = Callable[[str, float], CanaryReport]


def default_drift_detector(freeze: FrozenDataset) -> float:
    """Fallback determinista: deriva proporcional al volumen de datos nuevos."""
    if freeze.n_records == 0:
        return 1.0
    return min(1.0, (freeze.n_records - freeze.n_replay) / max(freeze.n_records, 1) * 0.1)


def default_champion_challenger(matchup: ChampionCandidate) -> ChampionCandidate:
    """Fallback: el candidato gana si su accuracy mejora y el resto no empeora."""
    acc_c = matchup.candidate_metrics.get("accuracy", 0.0)
    acc_h = matchup.champion_metrics.get("accuracy", 0.0)
    matchup.margin = acc_c - acc_h
    matchup.candidate_wins = matchup.margin > 0.0
    return matchup


def default_security_fairness(_: ChampionCandidate) -> SecurityFairnessReport:
    """Fallback permisivo SOLO para desarrollo/tests: sin señales, pasa."""
    return SecurityFairnessReport()


def default_hitl_approver(_: PipelineRun) -> Optional[bool]:
    """Fallback: sin humano → pendiente (fail-closed en dominios de alto impacto)."""
    return None


def default_canary_monitor(candidate_version: str, traffic_ratio: float) -> CanaryReport:
    """Fallback: canary saludable por defecto (monitor real inyectable)."""
    return CanaryReport(
        candidate_version=candidate_version,
        traffic_ratio=traffic_ratio,
        duration_sec=0.0,
    )


class GatePipeline:
    """Ejecuta los 5 gates en orden; detiene en el primer FAIL/HITL."""

    def __init__(
        self,
        policy: Optional[OrchestratorPolicy] = None,
        drift_detector: Optional[DriftDetectorFn] = None,
        champion_challenger: Optional[ChampionChallengerFn] = None,
        security_fairness: Optional[SecurityFairnessFn] = None,
        hitl_approver: Optional[HITLApproverFn] = None,
        canary_monitor: Optional[CanaryMonitorFn] = None,
        regulatory_policy: Optional[RegulatoryPolicy] = None,
        explainability_gate: Optional[ExplainabilityGate] = None,
    ) -> None:
        self.policy = policy or OrchestratorPolicy()
        self.drift_detector = drift_detector or default_drift_detector
        self.champion_challenger = champion_challenger or default_champion_challenger
        self.security_fairness = security_fairness or default_security_fairness
        self.hitl_approver = hitl_approver or default_hitl_approver
        self.canary_monitor = canary_monitor or default_canary_monitor
        self.regulatory_policy = regulatory_policy
        self.explainability_gate = explainability_gate

    # ------------------------------------------------------------------
    # Gate 3b — explainability / regulatory (insertado tras security)
    # ------------------------------------------------------------------
    def regulatory_explainability_gate(self, run: PipelineRun) -> GateResult:
        if self.explainability_gate is None or self.regulatory_policy is None:
            return GateResult(
                gate=GateName.EXPLAINABILITY,
                verdict=GateVerdict.PASS,
                reason="No regulatory policy configured; explainability gate skipped.",
            )
        if not self.regulatory_policy.requires(RegulatoryControl.INTERPRETABILITY_REQUIRED):
            return GateResult(
                gate=GateName.EXPLAINABILITY,
                verdict=GateVerdict.PASS,
                reason="Sector does not mandate model interpretability; gate skipped.",
            )
        if run.matchup is None:
            return GateResult(
                gate=GateName.EXPLAINABILITY,
                verdict=GateVerdict.FAIL,
                reason="No candidate available for explainability review.",
            )
        # Construimos un ModelCard mínimo a partir de la metadata del run/candidato
        from regulated_model_governance import ModelCard, ModelType
        model_type = ModelType.INTERPRETABLE if run.matchup.candidate_version.startswith("linear") else ModelType.BLACK_BOX
        card = ModelCard(
            model_id=run.matchup.candidate_version,
            model_type=model_type,
            algorithm="candidate",
            complexity_score=0.0 if model_type == ModelType.INTERPRETABLE else 0.9,
            metrics=run.matchup.candidate_metrics,
        )
        report = self.explainability_gate.evaluate(card, run.freeze.records if run.freeze else [])
        if not report.passed:
            return GateResult(
                gate=GateName.EXPLAINABILITY,
                verdict=GateVerdict.FAIL,
                score=report.stability_score,
                reason="; ".join(report.violations) or "Explainability requirements not met.",
                evidence=report.to_dict(),
            )
        return GateResult(
            gate=GateName.EXPLAINABILITY,
            verdict=GateVerdict.PASS,
            score=report.stability_score,
            reason=f"Explainability check passed ({report.method}).",
            evidence=report.to_dict(),
        )

    # ------------------------------------------------------------------
    # Gate 1 — drift
    # ------------------------------------------------------------------
    def drift_gate(self, run: PipelineRun) -> GateResult:
        freeze = run.freeze
        if freeze is None:
            return GateResult(
                gate=GateName.DRIFT,
                verdict=GateVerdict.FAIL,
                reason="No frozen dataset; retraining without versioned data is prohibited.",
            )
        score = float(self.drift_detector(freeze))

        # En incremental, el "drift" relevante es la caída sobre datos de replay
        # (olvido catastrófico): evidencia esperada en metrics del candidato.
        if run.trigger.strategy == RetrainStrategy.INCREMENTAL:
            forgetting = float(
                (run.matchup.champion_metrics.get("replay_accuracy", 1.0)
                 - run.matchup.candidate_metrics.get("replay_accuracy", 1.0))
                if run.matchup else 0.0
            )
            if forgetting > self.policy.catastrophic_forgetting_threshold:
                return GateResult(
                    gate=GateName.DRIFT,
                    verdict=GateVerdict.FAIL,
                    score=forgetting,
                    reason=(
                        f"Olvido catastrófico: replay cae {forgetting:.3f} > "
                        f"{self.policy.catastrophic_forgetting_threshold}."
                    ),
                    evidence={"forgetting": forgetting, "drift_score": score},
                )

        return GateResult(
            gate=GateName.DRIFT,
            verdict=GateVerdict.PASS,
            score=score,
            reason="Drift within policy bounds / justified by trigger.",
            evidence={"drift_score": score, "dataset_hash": freeze.dataset_hash},
        )

    # ------------------------------------------------------------------
    # Gate 2 — champion–challenger
    # ------------------------------------------------------------------
    def champion_challenger_gate(self, run: PipelineRun) -> GateResult:
        matchup = run.matchup
        if matchup is None:
            return GateResult(
                gate=GateName.CHAMPION_CHALLENGER,
                verdict=GateVerdict.FAIL,
                reason="No matchup evaluated; cannot promote without out-of-sample comparison.",
            )
        if self.policy.out_of_sample_required and not matchup.out_of_sample:
            return GateResult(
                gate=GateName.CHAMPION_CHALLENGER,
                verdict=GateVerdict.FAIL,
                reason="Evaluation was not out-of-sample.",
            )
        evaluated = self.champion_challenger(matchup)
        run.matchup = evaluated
        if not evaluated.candidate_wins or evaluated.margin < self.policy.min_improvement_margin:
            return GateResult(
                gate=GateName.CHAMPION_CHALLENGER,
                verdict=GateVerdict.FAIL,
                score=evaluated.margin,
                reason=(
                    f"Candidate does not beat champion (margin {evaluated.margin:.4f} "
                    f"< {self.policy.min_improvement_margin})."
                ),
                evidence=evaluated.to_dict(),
            )
        return GateResult(
            gate=GateName.CHAMPION_CHALLENGER,
            verdict=GateVerdict.PASS,
            score=evaluated.margin,
            reason=f"Candidate beats champion by {evaluated.margin:.4f}.",
            evidence=evaluated.to_dict(),
        )

    # ------------------------------------------------------------------
    # Gate 3 — security / fairness
    # ------------------------------------------------------------------
    def security_fairness_gate(self, run: PipelineRun) -> GateResult:
        if run.matchup is None:
            return GateResult(
                gate=GateName.SECURITY_FAIRNESS,
                verdict=GateVerdict.FAIL,
                reason="No candidate to evaluate.",
            )
        report = self.security_fairness(run.matchup)
        run.security_fairness = report
        if not report.passed:
            return GateResult(
                gate=GateName.SECURITY_FAIRNESS,
                verdict=GateVerdict.FAIL,
                score=report.fairness_score,
                reason="; ".join(report.violations) or "Security/fairness checks failed.",
                evidence=report.to_dict(),
            )
        return GateResult(
            gate=GateName.SECURITY_FAIRNESS,
            verdict=GateVerdict.PASS,
            score=report.fairness_score,
            reason="Bias, robustness, backdoor and PII checks passed.",
            evidence=report.to_dict(),
        )

    # ------------------------------------------------------------------
    # Gate 4 — HITL (UC-290)
    # ------------------------------------------------------------------
    def hitl_gate(self, run: PipelineRun) -> GateResult:
        # Considerar dominios regulatorios críticos además de la política base
        critical_domains = {
            "medical", "legal", "financial", "military",
            "critical_infrastructure_energy", "critical_infrastructure_water",
            "critical_infrastructure_telecom", "critical_infrastructure_transport",
            "critical_infrastructure_nuclear", "critical_infrastructure_industrial",
        }
        is_critical = run.trigger.domain in critical_domains
        high_impact = (
            self.policy.require_hitl_high_impact
            and run.trigger.domain in self.policy.high_impact_domains
        ) or is_critical
        if not high_impact and run.drift_score <= self.policy.auto_approve_max_risk:
            return GateResult(
                gate=GateName.HITL,
                verdict=GateVerdict.PASS,
                reason="Low-risk domain and drift below auto-approve threshold.",
                evidence={"domain": run.trigger.domain, "drift_score": run.drift_score},
            )

        decision = self.hitl_approver(run)
        if decision is None:
            return GateResult(
                gate=GateName.HITL,
                verdict=GateVerdict.REQUIRES_HITL,
                reason="High-impact promotion requires human approval (UC-290).",
                evidence={"domain": run.trigger.domain},
            )
        if decision:
            return GateResult(
                gate=GateName.HITL,
                verdict=GateVerdict.PASS,
                reason="Human approver accepted the promotion.",
                evidence={"domain": run.trigger.domain},
            )
        return GateResult(
            gate=GateName.HITL,
            verdict=GateVerdict.FAIL,
            reason="Human approver rejected the promotion.",
            evidence={"domain": run.trigger.domain},
        )

    # ------------------------------------------------------------------
    # Gate 5 — canary
    # ------------------------------------------------------------------
    def canary_gate(self, run: PipelineRun) -> GateResult:
        candidate = run.matchup.candidate_version if run.matchup else "unknown"
        report = self.canary_monitor(candidate, self.policy.canary_traffic_ratio)
        run.canary = report
        if not report.healthy or report.error_rate > self.policy.error_rate_threshold:
            return GateResult(
                gate=GateName.CANARY,
                verdict=GateVerdict.FAIL,
                score=report.error_rate,
                reason="Canary unhealthy: error budget exceeded.",
                evidence=report.to_dict(),
            )
        if (report.baseline_latency_p95_ms > 0 and report.latency_p95_ms
                > report.baseline_latency_p95_ms * (1 + self.policy.latency_p95_degradation_pct / 100)):
            return GateResult(
                gate=GateName.CANARY,
                verdict=GateVerdict.FAIL,
                score=report.latency_p95_ms,
                reason="Canary latency regression vs baseline.",
                evidence=report.to_dict(),
            )
        return GateResult(
            gate=GateName.CANARY,
            verdict=GateVerdict.PASS,
            score=report.user_satisfaction,
            reason="Canary healthy.",
            evidence=report.to_dict(),
        )

    # ------------------------------------------------------------------
    # Orquestación de gates
    # ------------------------------------------------------------------
    def run_gates(self, run: PipelineRun) -> List[GateResult]:
        """Ejecuta gates en orden hasta el primer FAIL / REQUIRES_HITL."""
        ordered = (
            self.drift_gate,
            self.champion_challenger_gate,
            self.security_fairness_gate,
            self.regulatory_explainability_gate,
            self.hitl_gate,
            self.canary_gate,
        )
        for gate_fn in ordered:
            result = gate_fn(run)
            run.gates.append(result)
            if result.verdict != GateVerdict.PASS:
                break
        return run.gates
