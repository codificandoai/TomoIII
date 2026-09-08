"""
UC-290 — Constructor del Expediente de Decisión.

El Expediente de Decisión es el artefacto central del HITL.
Consolida:
- Datos procesados (validados por UC-087 + UC-162).
- Razonamiento paso a paso (de UC-329 GraphRAG-GoT).
- Auto-evaluación de calidad (de UC-325).
- Conflicto detectado (de UC-322, si aplica).
- Score de confianza (calculado por RiskAssessor).
- Nivel de riesgo (calculado por RiskAssessor).
- Sugerencia de acción.
- Estado: [auto_execute | escalate_to_human].
"""

import time
from typing import Dict, Any, List

from models_290 import (
    DecisionDossier,
    DecisionInput,
    RiskAssessment,
    ReasoningStep,
    ReasoningStepType,
    DossierStatus,
    HITLDecision,
    generate_id,
)


class DossierBuilder:
    """Construye el Expediente de Decisión a partir de los inputs."""

    def build(
        self,
        decision_input: DecisionInput,
        risk_assessment: RiskAssessment,
        escalation_timeout_sec: float = 3600.0,
    ) -> DecisionDossier:
        """
        Construye el expediente consolidando todos los componentes.
        """
        dossier = DecisionDossier(
            dossier_id=generate_id(),
            trace_id=decision_input.trace_id or generate_id(),
            timestamp=time.time(),
            decision_input=decision_input,
            risk_assessment=risk_assessment,
            ai_suggestion=decision_input.ai_suggestion,
            ai_confidence=decision_input.ai_confidence,
            expires_at=time.time() + escalation_timeout_sec,
        )

        # Consolidar razonamiento paso a paso
        dossier.reasoning_steps = self._consolidate_reasoning(decision_input, risk_assessment)

        # Determinar estado y decisión
        if risk_assessment.requires_escalation:
            dossier.status = DossierStatus.PENDING_REVIEW
            dossier.decision = HITLDecision.ESCALATE
        else:
            dossier.status = DossierStatus.AUTO_EXECUTED
            dossier.decision = HITLDecision.AUTO_EXECUTE

        # Calcular hash de integridad
        dossier.compute_hash()

        return dossier

    def _consolidate_reasoning(
        self,
        decision_input: DecisionInput,
        risk_assessment: RiskAssessment,
    ) -> List[ReasoningStep]:
        """
        Consolida el razonamiento de todas las fuentes en pasos ordenados.
        """
        steps: List[ReasoningStep] = []
        step_num = 1

        # Pasos de la IA (UC-315)
        for s in decision_input.ai_reasoning_steps:
            if isinstance(s, ReasoningStep):
                steps.append(ReasoningStep(
                    step_number=step_num,
                    step_type=s.step_type,
                    description=s.description,
                    evidence=s.evidence,
                    confidence=s.confidence,
                    source=s.source or "uc315",
                ))
            elif isinstance(s, dict):
                steps.append(ReasoningStep(
                    step_number=step_num,
                    step_type=ReasoningStepType(s.get("step_type", "inference")),
                    description=s.get("description", ""),
                    evidence=s.get("evidence", ""),
                    confidence=s.get("confidence", 0.0),
                    source=s.get("source", "uc315"),
                ))
            step_num += 1

        # Paso: Validación UC-087
        if decision_input.uc087_integrity_passed:
            steps.append(ReasoningStep(
                step_number=step_num,
                step_type=ReasoningStepType.VALIDATION,
                description="UC-087: Integridad criptográfica validada (hash, firma, adversariales).",
                evidence=str(decision_input.uc087_integrity_details),
                confidence=1.0,
                source="uc087",
            ))
        else:
            steps.append(ReasoningStep(
                step_number=step_num,
                step_type=ReasoningStepType.VALIDATION,
                description="UC-087: Integridad criptográfica RECHAZADA.",
                evidence=str(decision_input.uc087_integrity_details),
                confidence=0.0,
                source="uc087",
            ))
        step_num += 1

        # Paso: Validación UC-162
        if decision_input.uc162_llmops_passed:
            steps.append(ReasoningStep(
                step_number=step_num,
                step_type=ReasoningStepType.VALIDATION,
                description="UC-162: LLMOps validado (sesgo, linaje, hallucination, drift).",
                evidence=str(decision_input.uc162_llmops_details),
                confidence=1.0,
                source="uc162",
            ))
        else:
            steps.append(ReasoningStep(
                step_number=step_num,
                step_type=ReasoningStepType.VALIDATION,
                description="UC-162: LLMOps RECHAZADO (sesgo, hallucination o drift detectado).",
                evidence=str(decision_input.uc162_llmops_details),
                confidence=0.0,
                source="uc162",
            ))
        step_num += 1

        # Paso: Auto-reflexión UC-325
        steps.append(ReasoningStep(
            step_number=step_num,
            step_type=ReasoningStepType.REFLECTION,
            description=f"UC-325: Auto-reflexión score = {decision_input.uc325_reflection_score:.2f}.",
            evidence=str(decision_input.uc325_reflection_details),
            confidence=decision_input.uc325_reflection_score,
            source="uc325",
        ))
        step_num += 1

        # Paso: Conflicto UC-322
        if decision_input.uc322_conflict_detected:
            steps.append(ReasoningStep(
                step_number=step_num,
                step_type=ReasoningStepType.CONFLICT,
                description="UC-322: Conflicto detectado entre agentes.",
                evidence=str(decision_input.uc322_conflict_details),
                confidence=0.0,
                source="uc322",
            ))
        else:
            steps.append(ReasoningStep(
                step_number=step_num,
                step_type=ReasoningStepType.CONFLICT,
                description="UC-322: Sin conflictos detectados.",
                evidence="",
                confidence=1.0,
                source="uc322",
            ))
        step_num += 1

        # Paso: Razonamiento graph UC-329
        if decision_input.uc329_graph_paths:
            steps.append(ReasoningStep(
                step_number=step_num,
                step_type=ReasoningStepType.INFERENCE,
                description=f"UC-329: {len(decision_input.uc329_graph_paths)} caminos de razonamiento explorados.",
                evidence=str(decision_input.uc329_graph_paths[:3]),
                confidence=0.8,
                source="uc329",
            ))
        step_num += 1

        # Paso: Evaluación de riesgo
        steps.append(ReasoningStep(
            step_number=step_num,
            step_type=ReasoningStepType.PROJECTION,
            description=(
                f"Evaluación de riesgo: score={risk_assessment.risk_score:.2f}, "
                f"nivel={risk_assessment.risk_level.value}, "
                f"confianza={risk_assessment.confidence_score:.2f}, "
                f"volatilidad={risk_assessment.volatility:.2%}."
            ),
            evidence=str(risk_assessment.factors),
            confidence=risk_assessment.confidence_score,
            source="uc290_risk",
        ))
        step_num += 1

        # Paso: Sugerencia final
        if risk_assessment.requires_escalation:
            steps.append(ReasoningStep(
                step_number=step_num,
                step_type=ReasoningStepType.SUGGESTION,
                description=(
                    f"SUGERENCIA: ESCALAR A HUMANO. Razones: "
                    f"{'; '.join(risk_assessment.escalation_reasons)}"
                ),
                evidence="",
                confidence=0.0,
                source="uc290",
            ))
        else:
            steps.append(ReasoningStep(
                step_number=step_num,
                step_type=ReasoningStepType.SUGGESTION,
                description=(
                    f"SUGERENCIA: Auto-ejecutar '{decision_input.ai_suggestion}' "
                    f"(confianza={risk_assessment.confidence_score:.2f}, "
                    f"riesgo={risk_assessment.risk_score:.2f})."
                ),
                evidence="",
                confidence=risk_assessment.confidence_score,
                source="uc290",
            ))

        return steps

    def to_summary(self, dossier: DecisionDossier) -> str:
        """Genera un resumen ejecutivo del expediente para el humano."""
        risk = dossier.risk_assessment
        risk_level = risk.risk_level.value if risk else "N/A"
        confidence = risk.confidence_score if risk else 0.0
        lines = [
            f"EXPEDIENTE DE DECISIÓN #{dossier.dossier_id[:8]}",
            f"Trace: {dossier.trace_id[:8]}",
            f"Estado: {dossier.status.value}",
            f"Decisión: {dossier.decision.value}",
            f"Sugerencia IA: {dossier.ai_suggestion}",
            f"Confianza IA: {dossier.ai_confidence:.2f}",
            f"Riesgo: {risk_level}",
            f"Confianza combinada: {confidence:.2f}",
            "",
            "RAZONAMIENTO PASO A PASO:",
        ]
        for step in dossier.reasoning_steps:
            lines.append(f"  {step.step_number}. [{step.source}] {step.description}")
        if dossier.risk_assessment and dossier.risk_assessment.requires_escalation:
            lines.append("")
            lines.append("RAZONES DE ESCALAMIENTO:")
            for reason in dossier.risk_assessment.escalation_reasons:
                lines.append(f"  - {reason}")
        return "\n".join(lines)
