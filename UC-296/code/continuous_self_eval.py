"""Autoevaluación continua del agente AGI para UC-296."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from memory_types import PerformanceEpisode
from self_model_store import SelfModelStore


class ContinuousSelfEvaluator:
    """Registra episodios de desempeño y propone ajustes de políticas.

    Cada episodio incluye:
    - tarea ejecutada,
    - éxito/fracaso,
    - métricas (reward, error, drawdown, etc.),
    - contexto (símbolo, estrategia, precio),
    - ajustes de política derivados.

    A partir de los episodios se generan reflexiones para la metacognición y se
    actualiza el self-model (competencias y confianza).
    """

    def __init__(self, self_model_store: Optional[SelfModelStore] = None) -> None:
        self.store = self_model_store or SelfModelStore()

    def evaluate_execution(
        self,
        task: str,
        success: bool,
        metrics: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> PerformanceEpisode:
        metrics = metrics or {}
        context = context or {}
        policy_adjustments = self._derive_policy_adjustments(metrics, context)
        episode = PerformanceEpisode(
            episode_id=str(uuid.uuid4())[:8],
            timestamp=datetime.now(timezone.utc).isoformat(),
            task=task,
            success=success,
            metrics=metrics,
            context=context,
            policy_adjustments=policy_adjustments,
        )
        self.store.record_performance(
            task=task,
            success=success,
            metrics=metrics,
            context=context,
            policy_adjustments=policy_adjustments,
        )
        self._update_competence(context, success)
        return episode

    def reflect(self, limit: int = 10) -> Dict[str, Any]:
        history = self.store.get_recent_performance(limit=limit)
        if not history:
            return {"reflection": "No hay episodios registrados todavía.", "suggestions": []}
        success_rate = sum(1 for h in history if h.get("success")) / len(history)
        avg_reward = sum(
            h.get("metrics", {}).get("reward", 0.0) for h in history
        ) / len(history)
        suggestions: List[str] = []
        if success_rate < 0.5:
            suggestions.append("La tasa de éxito es baja; considerar aumentar validación Juice/Safety.")
        if avg_reward < 0:
            suggestions.append("Recompensa promedio negativa; revisar estrategia o parámetros de riesgo.")
        if any(h.get("metrics", {}).get("drawdown_violated") for h in history):
            suggestions.append("Se detectaron violaciones de drawdown; ajustar stop_loss o exposición.")
        return {
            "sample_size": len(history),
            "success_rate": round(success_rate, 4),
            "avg_reward": round(avg_reward, 6),
            "reflection": (
                f"En los últimos {len(history)} episodios, éxito={success_rate:.2%}, "
                f"reward promedio={avg_reward:.4f}."
            ),
            "suggestions": suggestions,
        }

    def _derive_policy_adjustments(
        self,
        metrics: Dict[str, Any],
        context: Dict[str, Any],
    ) -> List[str]:
        adjustments: List[str] = []
        if metrics.get("drawdown_violated"):
            adjustments.append("Reducir tamaño de posición máxima un 10%.")
        if metrics.get("prediction_error", 0.0) > 0.05:
            adjustments.append("Solicitar más ticks de entrenamiento para el world model.")
        if not metrics.get("juice_approved", True):
            adjustments.append("Aumentar peso del filtro Juice en selección de estrategias.")
        if context.get("market_regime") == "high_volatility":
            adjustments.append("Activar modo conservador temporal.")
        return adjustments

    def _update_competence(self, context: Dict[str, Any], success: bool) -> None:
        competence = context.get("competence", "general")
        score = 1.0 if success else 0.0
        self.store.update_competence(competence, score)
