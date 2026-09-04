"""Persistencia y gestión del self-model del agente AGI para UC-296."""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "UC-295", "code")))

from memory_config import SelfModelConfig, StructuredMemoryConfig
from memory_types import PerformanceEpisode
from structured_memory import StructuredMemory


class SelfModelStore:
    """Mantiene el autoconocimiento del agente entre sesiones y gestiona su
    historial de desempeño.

    Capacidades soportadas:
    - Cargar/guardar el self-model (objetivos, competencias, límites, preferencias).
    - Registrar episodios de desempeño con métricas y contexto.
    - Recuperar episodios relevantes para reflexión y ajuste de políticas.
    """

    DEFAULT_GOAL = "Maximizar retorno ajustado por riesgo"

    def __init__(self, config: Optional[SelfModelConfig] = None) -> None:
        self.config = config or SelfModelConfig()
        self.structured = StructuredMemory(
            StructuredMemoryConfig(sqlite_path=self.config.sqlite_path)
        )
        self._cache: Optional[Dict[str, Any]] = None

    def load(self) -> Dict[str, Any]:
        if self._cache is not None:
            return self._cache
        data = self.structured.get_self_model()
        if data is None:
            data = self._default_self_model()
            self.structured.save_self_model(data)
        self._cache = data
        return data

    def save(self, data: Dict[str, Any]) -> None:
        data["last_updated"] = datetime.now(timezone.utc).isoformat()
        self.structured.save_self_model(data)
        self._cache = data

    def update_goal(self, new_goal: str, reason: str = "") -> Dict[str, Any]:
        model = self.load()
        model["current_goal"] = new_goal
        model.setdefault("goal_history", []).append({
            "goal": new_goal,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self.save(model)
        return model

    def update_competence(self, competence: str, score: float) -> Dict[str, Any]:
        model = self.load()
        profile = model.setdefault("competence_profile", {})
        old = profile.get(competence, score)
        profile[competence] = round(0.8 * old + 0.2 * score, 4)
        self.save(model)
        return model

    def record_performance(
        self,
        task: str,
        success: bool,
        metrics: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        policy_adjustments: Optional[List[str]] = None,
    ) -> PerformanceEpisode:
        episode = PerformanceEpisode(
            episode_id=str(uuid.uuid4())[:8],
            timestamp=datetime.now(timezone.utc).isoformat(),
            task=task,
            success=success,
            metrics=metrics or {},
            context=context or {},
            policy_adjustments=policy_adjustments or [],
        )
        self.structured.save_performance(episode.to_dict())
        # Recalibrar confianza del self-model según desempeño reciente
        self._update_confidence_from_history()
        return episode

    def get_recent_performance(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self.structured.get_performance_history(limit=limit)

    def get_summary(self) -> Dict[str, Any]:
        model = self.load()
        history = self.get_recent_performance(limit=1000)
        successes = sum(1 for h in history if h.get("success"))
        attempts = len(history)
        return {
            "self_model": model,
            "performance_attempts": attempts,
            "performance_successes": successes,
            "success_rate": round(successes / attempts, 4) if attempts else 0.0,
            "recent_policy_adjustments": [
                adj for h in history for adj in h.get("policy_adjustments", [])
            ][-10:],
        }

    def _default_self_model(self) -> Dict[str, Any]:
        return {
            "self_model_id": str(uuid.uuid4())[:8],
            "agent_identity": "UC296.Alpha",
            "current_goal": self.DEFAULT_GOAL,
            "goal_history": [],
            "competence_profile": {
                "technical_analysis": 0.8,
                "sentiment_analysis": 0.7,
                "risk_assessment": 0.9,
                "tick_prediction": 0.75,
                "memory_management": 0.8,
                "metacognition": 0.7,
            },
            "confidence_level": 1.0,
            "cognitive_load": "LOW",
            "recent_errors": 0,
            "max_memory_items": 7,
            "operational_limits": {
                "max_position_pct": 0.2,
                "max_drawdown_pct": 0.05,
                "max_trade_notional": 100_000.0,
            },
            "preferences": {
                "risk_tolerance": "moderate",
                "require_confirmation": True,
            },
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    def _update_confidence_from_history(self) -> None:
        history = self.get_recent_performance(limit=20)
        if not history:
            return
        success_rate = sum(1 for h in history if h.get("success")) / len(history)
        model = self.load()
        model["confidence_level"] = round(success_rate, 4)
        model["recent_errors"] = len(history) - int(success_rate * len(history))
        self.save(model)
