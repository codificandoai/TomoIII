"""
UC-308 — Asesor de mitigación.

Genera recomendaciones SIN auto-modificar código, prompts, políticas ni selectores.
Las acciones son: alertar, aumentar HITL (UC-290), deshabilitar tool (UC-300) o
solicitar contención/rollback (UC-324).
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

from models_308 import (
    DriftSignal,
    DriftStatus,
    DriftType,
    Recommendation,
    RecommendationAction,
    SystemStatus,
)


class MitigationAdvisor:
    """
    Mapea señales de deriva a recomendaciones de mitigación conservadoras.
    Nunca auto-aplica cambios; todas las acciones requieren aprobación humana.
    """

    def recommend(
        self,
        system_status: SystemStatus,
        signals: Sequence[DriftSignal],
        affected_tools: Sequence[str],
    ) -> List[Recommendation]:
        recommendations: List[Recommendation] = []

        # Siempre alertar al equipo.
        recommendations.append(Recommendation(
            action=RecommendationAction.ALERT_TEAM,
            target_tool="all",
            reason=f"System status is {system_status.value}. Manual review required.",
            auto_apply=False,
        ))

        # Recomendaciones por tipo de deriva.
        for signal in signals:
            tool = signal.tool or (affected_tools[0] if affected_tools else "unknown")
            if signal.drift_type == DriftType.QUALITY and signal.status in (DriftStatus.DEGRADED, DriftStatus.CRITICAL):
                recommendations.append(Recommendation(
                    action=RecommendationAction.INCREASE_HITL_UC290,
                    target_tool=tool,
                    reason=f"Quality degraded in {tool}: {signal.message}",
                    auto_apply=False,
                ))
            if signal.drift_type == DriftType.TOOL_OPERATIONAL and signal.status in (DriftStatus.DEGRADED, DriftStatus.CRITICAL):
                recommendations.append(Recommendation(
                    action=RecommendationAction.INCREASE_HITL_UC290,
                    target_tool=tool,
                    reason=f"Operational issues in {tool}: {signal.message}",
                    auto_apply=False,
                ))
            if signal.drift_type == DriftType.BEHAVIORAL and signal.status in (DriftStatus.DEGRADED, DriftStatus.CRITICAL):
                recommendations.append(Recommendation(
                    action=RecommendationAction.INCREASE_HITL_UC290,
                    target_tool=tool,
                    reason=f"Behavioral drift in {tool}: {signal.message}",
                    auto_apply=False,
                ))
            if signal.drift_type == DriftType.CONTRACT_API and signal.status in (DriftStatus.DEGRADED, DriftStatus.CRITICAL):
                recommendations.append(Recommendation(
                    action=RecommendationAction.DISABLE_TOOL_UC300,
                    target_tool=tool,
                    reason=f"API contract drift in {tool}: schema changed; disable until fix.",
                    auto_apply=False,
                ))
            if signal.drift_type == DriftType.HTML_INTERFACE and signal.status in (DriftStatus.DEGRADED, DriftStatus.CRITICAL):
                recommendations.append(Recommendation(
                    action=RecommendationAction.DISABLE_TOOL_UC300,
                    target_tool=tool,
                    reason=f"HTML interface drift in {tool}: selectors changed; disable until fix.",
                    auto_apply=False,
                ))
            if signal.drift_type == DriftType.CONCEPT and signal.status in (DriftStatus.DEGRADED, DriftStatus.CRITICAL):
                recommendations.append(Recommendation(
                    action=RecommendationAction.RETRAIN_UC087,
                    target_tool=tool,
                    reason=f"Concept drift in {tool}: prediction distribution changed. Request retrain through UC-087/MLSecOps pipeline.",
                    auto_apply=False,
                ))

        # Si el estado es crítico, solicitar contención/rollback a UC-324.
        if system_status == SystemStatus.CRITICAL:
            recommendations.append(Recommendation(
                action=RecommendationAction.CONTAINMENT_ROLLBACK_UC324,
                target_tool="all",
                reason="Critical degradation detected. Request containment or rollback via UC-324.",
                auto_apply=False,
            ))

        # Deduplicar por acción + target_tool manteniendo orden.
        seen: set = set()
        unique: List[Recommendation] = []
        for rec in recommendations:
            key = (rec.action.value, rec.target_tool)
            if key not in seen:
                seen.add(key)
                unique.append(rec)
        return unique
