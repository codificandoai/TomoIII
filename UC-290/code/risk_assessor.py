"""
UC-290 — Evaluador de riesgo y confianza.

Calcula:
- Score de riesgo basado en múltiples factores.
- Score de confianza combinando IA + validaciones externas.
- Nivel de riesgo (none, low, medium, high, critical).
- Volatilidad del contexto.
- Factores que contribuyen al riesgo.
"""

import math
from typing import Dict, Any, List

from models_290 import (
    HITLConfig,
    DecisionInput,
    RiskAssessment,
    RiskLevel,
    ReasoningStep,
    ReasoningStepType,
)


class RiskAssessor:
    """Evalúa el riesgo y la confianza de una decisión de UC-315."""

    def __init__(self, config: HITLConfig = None):
        self.config = config or HITLConfig()

    def assess(self, decision_input: DecisionInput) -> RiskAssessment:
        """
        Evalúa el riesgo de una decisión.

        Factores considerados:
        1. Confianza de la IA (UC-315).
        2. Validación de integridad (UC-087).
        3. Validación LLMOps (UC-162).
        4. Score de auto-reflexión (UC-325).
        5. Conflictos detectados (UC-322).
        6. Volatilidad del contexto.
        7. Complejidad del razonamiento (UC-329).
        """
        factors: List[Dict[str, Any]] = []
        risk_components: List[float] = []
        confidence_components: List[float] = []

        # Factor 1: Confianza de la IA
        ai_conf = decision_input.ai_confidence
        if ai_conf < self.config.confidence_threshold:
            factors.append({
                "name": "ai_confidence_low",
                "value": ai_conf,
                "threshold": self.config.confidence_threshold,
                "contribution": "risk_increase",
                "weight": 0.20,
            })
            risk_components.append(0.20 * (1.0 - ai_conf))
        else:
            factors.append({
                "name": "ai_confidence_ok",
                "value": ai_conf,
                "contribution": "confidence_increase",
                "weight": 0.15,
            })
        confidence_components.append(ai_conf * 0.15)

        # Factor 2: Integridad UC-087
        if not decision_input.uc087_integrity_passed:
            factors.append({
                "name": "uc087_integrity_failed",
                "value": False,
                "contribution": "risk_critical",
                "weight": 0.30,
            })
            risk_components.append(0.30)
        else:
            factors.append({
                "name": "uc087_integrity_passed",
                "value": True,
                "contribution": "confidence_increase",
                "weight": 0.20,
            })
            confidence_components.append(0.20)

        # Factor 3: LLMOps UC-162
        if not decision_input.uc162_llmops_passed:
            factors.append({
                "name": "uc162_llmops_failed",
                "value": False,
                "contribution": "risk_high",
                "weight": 0.20,
            })
            risk_components.append(0.20)
        else:
            factors.append({
                "name": "uc162_llmops_passed",
                "value": True,
                "contribution": "confidence_increase",
                "weight": 0.15,
            })
            confidence_components.append(0.15)

        # Factor 4: Auto-reflexión UC-325
        reflection_score = decision_input.uc325_reflection_score
        if reflection_score < 0.5:
            factors.append({
                "name": "uc325_reflection_low",
                "value": reflection_score,
                "threshold": 0.5,
                "contribution": "risk_increase",
                "weight": 0.15,
            })
            risk_components.append(0.15 * (1.0 - reflection_score))
        confidence_components.append(reflection_score * 0.15)

        # Factor 5: Conflictos UC-322
        if decision_input.uc322_conflict_detected:
            factors.append({
                "name": "uc322_conflict_detected",
                "value": True,
                "contribution": "risk_high",
                "weight": 0.25,
            })
            risk_components.append(0.25)
        else:
            confidence_components.append(0.10)

        # Factor 6: Volatilidad del contexto
        volatility = self._calculate_volatility(decision_input)
        if volatility > self.config.volatility_threshold:
            factors.append({
                "name": "volatility_high",
                "value": volatility,
                "threshold": self.config.volatility_threshold,
                "contribution": "risk_increase",
                "weight": 0.15,
            })
            risk_components.append(min(0.15, volatility * 0.15 / self.config.volatility_threshold))

        # Factor 7: Complejidad del razonamiento (número de caminos UC-329)
        graph_paths = len(decision_input.uc329_graph_paths)
        if graph_paths > 5:
            factors.append({
                "name": "reasoning_complexity_high",
                "value": graph_paths,
                "contribution": "risk_increase",
                "weight": 0.05,
            })
            risk_components.append(0.05)

        # Calcular scores
        risk_score = min(1.0, sum(risk_components))
        confidence_score = min(1.0, sum(confidence_components))

        # Determinar nivel de riesgo
        risk_level = self._classify_risk(risk_score)

        # Determinar si requiere escalamiento
        requires_escalation = False
        escalation_reasons: List[str] = []

        if self.config.require_human_for_critical and risk_level == RiskLevel.CRITICAL:
            requires_escalation = True
            escalation_reasons.append("Riesgo crítico: requiere intervención humana obligatoria.")

        if self.config.require_human_for_high_risk and risk_level == RiskLevel.HIGH:
            requires_escalation = True
            escalation_reasons.append("Riesgo alto: requiere revisión humana antes de ejecución.")

        if confidence_score < self.config.confidence_threshold:
            requires_escalation = True
            escalation_reasons.append(
                f"Confianza baja ({confidence_score:.2f} < {self.config.confidence_threshold}): "
                "requiere validación humana."
            )

        if decision_input.uc087_integrity_passed is False:
            requires_escalation = True
            escalation_reasons.append("UC-087 rechazó integridad: bloqueo automático + escalamiento.")

        if decision_input.uc322_conflict_detected:
            requires_escalation = True
            escalation_reasons.append("UC-322 detectó conflicto entre agentes: requiere mediación humana.")

        if volatility > self.config.volatility_threshold:
            requires_escalation = True
            escalation_reasons.append(
                f"Volatilidad extrema ({volatility:.2%} > {self.config.volatility_threshold:.2%}): "
                "riesgo de flash crash."
            )

        return RiskAssessment(
            risk_score=risk_score,
            risk_level=risk_level,
            confidence_score=confidence_score,
            factors=factors,
            volatility=volatility,
            requires_escalation=requires_escalation,
            escalation_reasons=escalation_reasons,
        )

    def _calculate_volatility(self, decision_input: DecisionInput) -> float:
        """Calcula la volatilidad del contexto."""
        ctx = decision_input.context
        if "predicted_move" in ctx and "current_price" in ctx:
            price = ctx.get("current_price", 100.0)
            if price > 0:
                return abs(ctx["predicted_move"]) / price
        if "volatility" in ctx:
            return float(ctx["volatility"])
        # Estimar desde la varianza de valores numéricos
        numeric_vals = [v for v in ctx.values() if isinstance(v, (int, float))]
        if len(numeric_vals) > 1:
            mean = sum(numeric_vals) / len(numeric_vals)
            if mean != 0:
                variance = sum((v - mean) ** 2 for v in numeric_vals) / len(numeric_vals)
                return math.sqrt(variance) / abs(mean)
        return 0.0

    def _classify_risk(self, risk_score: float) -> RiskLevel:
        """Clasifica el score de riesgo en un nivel."""
        if risk_score >= self.config.risk_critical_threshold:
            return RiskLevel.CRITICAL
        if risk_score >= self.config.risk_high_threshold:
            return RiskLevel.HIGH
        if risk_score >= 0.40:
            return RiskLevel.MEDIUM
        if risk_score >= 0.15:
            return RiskLevel.LOW
        return RiskLevel.NONE
