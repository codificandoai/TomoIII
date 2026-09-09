"""UC-703 fine_tuning — Evaluación, promotion gate y alineación."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fine_tuning.models_ft import EvaluationReport


class EvaluationAgent:
    """
    Evaluación multi-juez con medición de olvido catastrófico.
    En producción delegaría a benchmarks y LLM judges; aquí simula determinísticamente.
    """

    def __init__(self, judges: Optional[List[str]] = None) -> None:
        self.judges = judges or ["gpt-4-judge", "claude-judge", "local-judge"]

    def evaluate(
        self,
        run_id: str,
        domain_results: List[Dict[str, Any]],
        general_results: List[Dict[str, Any]],
        baseline_general_score: float = 0.80,
    ) -> EvaluationReport:
        # Métricas simplificadas: accuracy promedio por conjunto.
        def avg(items: List[Dict[str, Any]]) -> float:
            if not items:
                return 0.0
            return sum(i.get("correct", 0) for i in items) / len(items)

        domain_score = avg(domain_results)
        general_score = avg(general_results)
        forgetting = baseline_general_score - general_score

        # Multi-juez: promedios simulados alrededor del domain score.
        judge_scores = {}
        for j in self.judges:
            import random
            random.seed(f"{run_id}-{j}")
            judge_scores[j] = round(min(1.0, max(0.0, domain_score + random.uniform(-0.05, 0.05))), 3)

        recommendations: List[str] = []
        if forgetting > 0.10:
            recommendations.append("catastrophic_forgetting_detected: add replay data")
        if domain_score < 0.70:
            recommendations.append("low_domain_score: increase domain examples")
        if any(s < 0.65 for s in judge_scores.values()):
            recommendations.append("judge_disagreement: review samples manually")

        return EvaluationReport(
            run_id=run_id,
            domain_score=round(domain_score, 3),
            general_score=round(general_score, 3),
            catastrophic_forgetting_score=round(forgetting, 3),
            judge_scores=judge_scores,
            passed=False,
            recommendations=recommendations,
        )


class PromotionGate:
    """
    Gate de promoción a producción. Exige rendimiento de dominio y límite de
    degradación general.
    """

    def __init__(
        self,
        min_domain_score: float = 0.75,
        max_forgetting: float = 0.08,
        min_judge_consensus: float = 0.70,
        require_hitl_for_high_risk: bool = True,
    ) -> None:
        self.min_domain_score = min_domain_score
        self.max_forgetting = max_forgetting
        self.min_judge_consensus = min_judge_consensus
        self.require_hitl_for_high_risk = require_hitl_for_high_risk

    def decide(self, report: EvaluationReport, approval_given: bool = False) -> Dict[str, Any]:
        reasons: List[str] = []
        passed = True
        if report.domain_score < self.min_domain_score:
            passed = False
            reasons.append(f"domain_score {report.domain_score} < {self.min_domain_score}")
        if report.catastrophic_forgetting_score > self.max_forgetting:
            passed = False
            reasons.append(f"forgetting {report.catastrophic_forgetting_score} > {self.max_forgetting}")
        min_judge = min(report.judge_scores.values()) if report.judge_scores else 0.0
        if min_judge < self.min_judge_consensus:
            passed = False
            reasons.append(f"min_judge_score {min_judge} < {self.min_judge_consensus}")

        # Si todo pasa, pero hay alertas fuertes, puede exigir HITL.
        needs_hitl = False
        if passed and report.catastrophic_forgetting_score > self.max_forgetting * 0.5:
            needs_hitl = True
            reasons.append("high_forgetting_alert_requires_hitl")

        if needs_hitl and self.require_hitl_for_high_risk and not approval_given:
            passed = False
            reasons.append("hitl_approval_required")

        report.passed = passed
        return {
            "passed": passed,
            "needs_hitl": needs_hitl,
            "reasons": reasons,
            "report": report.to_dict(),
        }


class AlignmentAgent:
    """
    Selecciona técnica de alineación (RLHF/DPO) según perfil de riesgo y genera
    reporte de compensación seguridad-utilidad.
    """

    def recommend(
        self,
        domain: str,
        risk_profile: str,  # low, medium, high, critical
        dataset_size: int,
        has_human_preferences: bool,
    ) -> Dict[str, Any]:
        if risk_profile in ("high", "critical"):
            method = "RLHF" if has_human_preferences else "Constitutional-AI"
            safety_weight = 0.8
            utility_weight = 0.2
        elif risk_profile == "medium":
            method = "DPO" if has_human_preferences else "SLiC"
            safety_weight = 0.6
            utility_weight = 0.4
        else:
            method = "DPO" if dataset_size > 1000 else "SFT"
            safety_weight = 0.4
            utility_weight = 0.6

        return {
            "recommended_method": method,
            "safety_weight": safety_weight,
            "utility_weight": utility_weight,
            "requires_hitl": risk_profile in ("high", "critical"),
            "trade_off_report": f"Method {method} selected for risk={risk_profile}; "
                               f"safety={safety_weight}, utility={utility_weight}",
        }
