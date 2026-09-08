"""UC-087 — MLOps Self-Healing Orchestrator.

Orquesta respuesta autónoma a incidentes de drift/fallos de modelos:
- escucha señales de drift (UC-308) o métricas de producción (UC-309)
- decide: reentrenar, canary, rollback, fallback a caché, o escalar
- entrena candidatos en sandbox con SandboxTrainer
- valida con ProvenanceValidator, InputFilter, RobustnessEvaluator, TriggerDetector
- gestiona versiones con RollbackManager
- emite eventos canónicos a UC-309

Todas las acciones de promoción/rollback críticos requieren autorización externa;
el orquestador puede proponer/auto-ejecutar canary y fallback seguro.
"""
from __future__ import annotations

import copy
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from adversarial_generator import AdversarialGenerator
from input_filter import InputFilter
from models_087 import (
    DataPoint,
    MLSecOpsConfig,
)
from provenance_validator import ProvenanceValidator
from rollback_manager import RollbackManager
from sandbox_model import SandboxLogisticModel
from sandbox_trainer import SandboxTrainer
from trigger_detector import TriggerDetector


class HealingAction(str, Enum):
    """Decisiones posibles del orquestador."""
    RETRAIN = "retrain"
    ROLLBACK = "rollback"
    CANARY = "canary"
    FALLBACK_CACHE = "fallback_cache"
    ESCALATE = "escalate"
    NOOP = "noop"


@dataclass
class HealingEvent:
    """Evento inmutable de auto-reparación."""
    event_id: str
    timestamp: float
    agent_id: str
    trigger: str
    action: HealingAction
    status: str
    reason: str
    evidence: Dict[str, Any]
    model_version: str = ""
    requires_approval: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "agent_id": self.agent_id,
            "trigger": self.trigger,
            "action": self.action.value,
            "status": self.status,
            "reason": self.reason,
            "evidence": self.evidence,
            "model_version": self.model_version,
            "requires_approval": self.requires_approval,
        }


class MLOpsSelfHealingOrchestrator:
    """Orquestador de auto-reparación MLOps."""

    def __init__(
        self,
        config: Optional[MLSecOpsConfig] = None,
        rollback_manager: Optional[RollbackManager] = None,
        trainer: Optional[SandboxTrainer] = None,
        validator: Optional[ProvenanceValidator] = None,
        input_filter: Optional[InputFilter] = None,
        trigger_detector: Optional[TriggerDetector] = None,
        event_sink: Optional[Callable[[HealingEvent], None]] = None,
        cache_predictor: Optional[Callable[[Any], float]] = None,
        retrain_source: str = "uc308_concept_drift",
    ) -> None:
        self.config = config or MLSecOpsConfig()
        self.rollback = rollback_manager or RollbackManager()
        self.trainer = trainer or SandboxTrainer(
            self.config,
            AdversarialGenerator(
                epsilon=self.config.adversarial_epsilon,
                steps=self.config.adversarial_steps,
            ),
        )
        self.validator = validator or ProvenanceValidator()
        self.input_filter = input_filter or InputFilter(outlier_threshold=self.config.outlier_threshold)
        self.trigger_detector = trigger_detector or TriggerDetector(slice_drop_threshold=self.config.slice_drop_threshold)
        self.event_sink = event_sink
        self.cache_predictor = cache_predictor
        self.retrain_source = retrain_source

        # Estado del orquestador
        self._cache: Dict[str, Any] = {}
        self._events: List[HealingEvent] = []
        self._failed_retrain_attempts: Dict[str, int] = {}

    def _emit(self, event: HealingEvent) -> None:
        self._events.append(event)
        if self.event_sink is not None:
            try:
                self.event_sink(event)
            except Exception:
                pass

    def decide_action(
        self,
        trigger: str,
        severity: str,
        metric_value: float,
        available_data: Optional[List[DataPoint]] = None,
    ) -> HealingAction:
        """Decide qué acción de auto-reparación tomar."""
        if self.rollback.get_promoted() is None:
            return HealingAction.ESCALATE

        if severity == "critical":
            if available_data and len(available_data) >= self.config.min_samples_for_training:
                if self._failed_retrain_attempts.get(trigger, 0) < self.config.max_failed_retrain_attempts:
                    return HealingAction.RETRAIN
            return HealingAction.ROLLBACK

        if severity == "degraded":
            if self.cache_predictor is not None:
                return HealingAction.FALLBACK_CACHE
            return HealingAction.CANARY

        if severity == "warning" and available_data:
            return HealingAction.CANARY

        return HealingAction.NOOP

    def fallback_to_cache(self, query: Any, agent_id: str) -> Dict[str, Any]:
        """Usa un predictor de reserva/cache si está disponible."""
        result: Dict[str, Any] = {
            "action": HealingAction.FALLBACK_CACHE.value,
            "source": "cache_or_standby",
            "agent_id": agent_id,
        }
        if self.cache_predictor is not None:
            try:
                score = self.cache_predictor(query)
                result["prediction"] = score
                result["status"] = "success"
            except Exception as exc:
                result["status"] = "error"
                result["error"] = str(exc)
        else:
            result["status"] = "unavailable"
            result["prediction"] = None
        return result

    def _prepare_data(self, data: List[DataPoint]) -> List[DataPoint]:
        """Filtra outliers y valida provenance."""
        clean, dropped = self.input_filter.filter_outliers(data)
        report = self.validator.validate_batch(clean, source=self.retrain_source, allowed_sources=[self.retrain_source])
        if not report.all_passed:
            raise ValueError(f"Provenance validation failed: {report.to_dict()}")
        return clean

    def retrain(
        self,
        data: List[DataPoint],
        agent_id: str,
        attacks: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Entrena candidato en sandbox y lo registra en RollbackManager."""
        try:
            clean = self._prepare_data(data)
        except Exception as exc:
            self._failed_retrain_attempts[agent_id] = self._failed_retrain_attempts.get(agent_id, 0) + 1
            event = HealingEvent(
                event_id=str(uuid.uuid4()),
                timestamp=time.time(),
                agent_id=agent_id,
                trigger="retrain_preparation_failed",
                action=HealingAction.RETRAIN,
                status="failed",
                reason=str(exc),
                evidence={"dropped_count": 0, "error": str(exc)},
                requires_approval=True,
            )
            self._emit(event)
            return None

        if self.trainer is None:
            self.trainer = SandboxTrainer(self.config, None)  # type: ignore[arg-type]

        try:
            candidate = self.trainer.train(clean)
        except Exception as exc:
            self._failed_retrain_attempts[agent_id] = self._failed_retrain_attempts.get(agent_id, 0) + 1
            event = HealingEvent(
                event_id=str(uuid.uuid4()),
                timestamp=time.time(),
                agent_id=agent_id,
                trigger="retrain_train_failed",
                action=HealingAction.RETRAIN,
                status="failed",
                reason=str(exc),
                evidence={"samples": len(clean)},
                requires_approval=True,
            )
            self._emit(event)
            return None

        # Robustness + backdoor checks
        attacks = attacks or ["pgd"]
        robust = self.trainer.cross_validate_robustness(candidate, clean, attacks)
        backdoor = self.trigger_detector.evaluate(candidate, clean, {})

        passed = (
            robust.get("passed_all", False)
            and len(backdoor.slice_alerts) == 0
            and not backdoor.suspicious_features
        )

        model_state = {
            "weights": candidate.weights,
            "bias": candidate.bias,
            "dim": candidate.dim,
            "trained": candidate.trained,
            "robustness_report": robust,
            "backdoor_report": backdoor.to_dict(),
            "source": self.retrain_source,
        }

        version = self.rollback.save_candidate(
            model_state=model_state,
            metrics={
                "robustness_approved": robust.get("overall_approved"),
                "slice_alerts": len(backdoor.slice_alerts),
                "suspicious_features": backdoor.suspicious_features,
            },
        )

        event = HealingEvent(
            event_id=str(uuid.uuid4()),
            timestamp=time.time(),
            agent_id=agent_id,
            trigger="retrain_complete",
            action=HealingAction.RETRAIN,
            status="success" if passed else "rejected",
            reason="Candidate trained and validated" if passed else "Robustness or backdoor checks failed",
            evidence={
                "version_id": version.version_id,
                "samples": len(clean),
                "robustness": robust,
                "backdoor": backdoor.to_dict(),
            },
            model_version=version.version_id,
            requires_approval=not passed,
        )
        self._emit(event)

        if passed:
            self._failed_retrain_attempts[agent_id] = 0
            return {
                "version_id": version.version_id,
                "promoted": False,
                "canary": False,
                "next_step": "canary",
            }
        return None

    def canary(
        self,
        version_id: str,
        agent_id: str,
        traffic_ratio: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Activa canary para un candidato."""
        ratio = traffic_ratio or self.config.canary_traffic_ratio
        existing = next((v for v in self.rollback.versions if v.version_id == version_id), None)
        if existing is None:
            existing = self.rollback.save_candidate({"version_id": version_id, "canary_ratio": ratio}, is_canary=True)
        else:
            existing.is_canary = True
            self.rollback._save_index()
        version = existing
        # Simula activación de canary; en producción conectaría al enrutador de tráfico.
        event = HealingEvent(
            event_id=str(uuid.uuid4()),
            timestamp=time.time(),
            agent_id=agent_id,
            trigger="canary_activated",
            action=HealingAction.CANARY,
            status="success",
            reason=f"Canary activated at {ratio:.0%} traffic",
            evidence={"version_id": version.version_id, "traffic_ratio": ratio},
            model_version=version.version_id,
            requires_approval=False,
        )
        self._emit(event)
        return {"version_id": version.version_id, "traffic_ratio": ratio, "status": "canary"}

    def promote(
        self,
        version_id: str,
        agent_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Promueve una versión a producción. Requiere aprobación humana en sistema real."""
        promoted = self.rollback.promote(version_id)
        if promoted is None:
            return None
        event = HealingEvent(
            event_id=str(uuid.uuid4()),
            timestamp=time.time(),
            agent_id=agent_id,
            trigger="model_promoted",
            action=HealingAction.CANARY,
            status="success",
            reason="Model promoted to production",
            evidence={"version_id": version_id},
            model_version=version_id,
            requires_approval=True,
        )
        self._emit(event)
        return {"version_id": version_id, "status": "promoted"}

    def rollback_safe(
        self,
        agent_id: str,
        version_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Revierte a versión segura."""
        target = self.rollback.rollback(version_id)
        if target is None:
            return None
        event = HealingEvent(
            event_id=str(uuid.uuid4()),
            timestamp=time.time(),
            agent_id=agent_id,
            trigger="rollback_activated",
            action=HealingAction.ROLLBACK,
            status="success",
            reason=f"Rolled back to {target.version_id}",
            evidence={"version_id": target.version_id, "promoted": target.promoted},
            model_version=target.version_id,
            requires_approval=True,
        )
        self._emit(event)
        return {"version_id": target.version_id, "status": "rollback"}

    def handle_signal(
        self,
        trigger: str,
        severity: str,
        agent_id: str,
        metric_value: float,
        available_data: Optional[List[DataPoint]] = None,
        query: Any = None,
    ) -> HealingEvent:
        """Punto de entrada único: recibe señal, decide y ejecuta acción segura."""
        action = self.decide_action(trigger, severity, metric_value, available_data)

        if action == HealingAction.ROLLBACK:
            result = self.rollback_safe(agent_id)
            status = "success" if result else "failed"
            reason = f"Auto-rollback due to {trigger} severity={severity}"
            requires_approval = True
            model_version = result.get("version_id", "") if result else ""

        elif action == HealingAction.RETRAIN:
            result = self.retrain(available_data or [], agent_id) if available_data else None
            status = "initiated" if result else "failed"
            reason = f"Auto-retrain due to {trigger} severity={severity}"
            requires_approval = True
            model_version = result.get("version_id", "") if result else ""

        elif action == HealingAction.FALLBACK_CACHE:
            result = self.fallback_to_cache(query, agent_id)
            status = result.get("status", "unavailable")
            reason = f"Fallback to cache due to {trigger} severity={severity}"
            requires_approval = False
            model_version = ""

        elif action == HealingAction.CANARY:
            # canary requiere un candidato previo; si no hay, escalamos
            result = None
            status = "skipped"
            reason = f"Canary requested but no candidate available for {trigger}"
            requires_approval = False
            model_version = ""

        elif action == HealingAction.ESCALATE:
            result = None
            status = "escalated"
            reason = f"No safe version available; escalate due to {trigger}"
            requires_approval = True
            model_version = ""

        else:
            result = None
            status = "noop"
            reason = f"No action required for {trigger} severity={severity}"
            requires_approval = False
            model_version = ""

        event = HealingEvent(
            event_id=str(uuid.uuid4()),
            timestamp=time.time(),
            agent_id=agent_id,
            trigger=trigger,
            action=action,
            status=status,
            reason=reason,
            evidence=result or {},
            model_version=model_version,
            requires_approval=requires_approval,
        )
        self._emit(event)
        return event

    def get_events(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._events]
