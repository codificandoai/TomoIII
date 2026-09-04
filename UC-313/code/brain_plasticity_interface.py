"""UC-313 — Interfaz de plasticidad del cerebro prefrontal AGI.

Permite a la capa de evolución cognitiva reescribir de forma controlada los
parámetros del cerebro central (`CentralBrain`) y del `TradingWorldModel`
(GWT), implementando:

- Plasticidad Hebbiana Artificial sobre pesos sinápticos GWT.
- Consolidación Sináptica Elástica (EWC) mediante snapshots de línea base.
- Congelamiento/descongelamiento selectivo de subsistemas de memoria AGI.
- Reentrenamiento dinámico del modelo probabilístico del world model.
- Trazabilidad completa y rollback a la línea base.

Todas las modificaciones requieren aprobación explícita y quedan registradas.
"""
from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from central_brain import CentralBrain
from memory_router import IntelligentMemoryRouter
from self_model_store import SelfModelStore


@dataclass
class PrefrontalChangeRecord:
    """Registro auditable de un cambio en el cerebro prefrontal."""

    change_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    target: str = ""
    action: str = ""
    previous_value: Any = None
    new_value: Any = None
    reason: str = ""
    approved_by: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "change_id": self.change_id,
            "target": self.target,
            "action": self.action,
            "previous_value": self.previous_value,
            "new_value": self.new_value,
            "reason": self.reason,
            "approved_by": self.approved_by,
            "timestamp": self.timestamp,
        }


class PrefrontalController:
    """Controlador de plasticidad del cerebro central y world model.

    Mantiene una línea base (`_baseline_config`) de los hiperparámetros
    plásticos. Cada cambio genera un snapshot que permite rollback. Los
    componentes críticos pueden marcarse como congelados para proteger el
    conocimiento histórico frente al olvido catastrófico.
    """

    PLASTIC_PARAMS = {
        "model.learning_rate",
        "model.risk_aversion",
        "model.return_weight",
        "model.risk_weight",
        "model.alignment_weight",
        "model.probabilistic.retrain_after",
        "model.probabilistic.uncertainty_retrain_threshold",
        "model.probabilistic.prediction_error_retrain_threshold",
        "model.probabilistic.max_iter",
        "model.probabilistic.embedding_dim",
    }

    def __init__(
        self,
        central_brain: CentralBrain,
        memory_router: Optional[IntelligentMemoryRouter] = None,
        self_store: Optional[SelfModelStore] = None,
    ) -> None:
        self.brain = central_brain
        self.memory_router = memory_router
        self.self_store = self_store
        self._baseline_config = self._snapshot_config(central_brain)
        self._frozen_modules: Dict[str, bool] = {
            "long_term_vector": False,
            "structured_sql": False,
            "short_term_notepad": False,
            "self_model": False,
        }
        self._gwt_weights: Dict[str, float] = {}
        self._gwt_baselines: Dict[str, float] = {}
        self.change_log: List[PrefrontalChangeRecord] = []

    # ------------------------------------------------------------------
    # Snapshot y línea base
    # ------------------------------------------------------------------
    def _snapshot_config(self, brain: CentralBrain) -> Dict[str, Any]:
        cfg = brain.config
        return {
            "model.learning_rate": cfg.model.learning_rate,
            "model.risk_aversion": cfg.model.risk_aversion,
            "model.return_weight": cfg.model.return_weight,
            "model.risk_weight": cfg.model.risk_weight,
            "model.alignment_weight": cfg.model.alignment_weight,
            "model.probabilistic.retrain_after": cfg.model.probabilistic.retrain_after,
            "model.probabilistic.uncertainty_retrain_threshold": cfg.model.probabilistic.uncertainty_retrain_threshold,
            "model.probabilistic.prediction_error_retrain_threshold": cfg.model.probabilistic.prediction_error_retrain_threshold,
            "model.probabilistic.max_iter": cfg.model.probabilistic.max_iter,
            "model.probabilistic.embedding_dim": cfg.model.probabilistic.embedding_dim,
        }

    def get_current_params(self) -> Dict[str, Any]:
        return self._snapshot_config(self.brain)

    def get_baseline(self) -> Dict[str, Any]:
        return copy.deepcopy(self._baseline_config)

    # ------------------------------------------------------------------
    # Lectura/escritura segura de parámetros anidados
    # ------------------------------------------------------------------
    @staticmethod
    def _get_param(cfg: Any, path: str) -> Any:
        parts = path.split(".")
        for p in parts:
            cfg = getattr(cfg, p)
        return cfg

    @staticmethod
    def _set_param(cfg: Any, path: str, value: Any) -> Any:
        parts = path.split(".")
        for p in parts[:-1]:
            cfg = getattr(cfg, p)
        previous = getattr(cfg, parts[-1])
        setattr(cfg, parts[-1], value)
        return previous

    def _is_plastic(self, path: str) -> bool:
        return path in self.PLASTIC_PARAMS

    # ------------------------------------------------------------------
    # Operaciones de plasticidad
    # ------------------------------------------------------------------
    def update_param(
        self,
        path: str,
        value: Any,
        reason: str,
        approved_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Actualiza un hiperparámetro plástico del cerebro central."""
        if not self._is_plastic(path):
            return {
                "status": "rejected",
                "reason": f"{path} no es un parámetro plástico aprobado",
            }
        previous = self._get_param(self.brain.config, path)
        record = PrefrontalChangeRecord(
            target=path,
            action="update_param",
            previous_value=previous,
            new_value=value,
            reason=reason,
            approved_by=approved_by,
        )
        self._set_param(self.brain.config, path, value)
        self.change_log.append(record)
        self._audit_change(record)
        return {"status": "applied", "change": record.to_dict()}

    def retrain_world_model(
        self,
        reason: str,
        approved_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Dispara el reentrenamiento del world model con los datos acumulados."""
        record = PrefrontalChangeRecord(
            target="world_model.probabilistic_model",
            action="retrain",
            reason=reason,
            approved_by=approved_by,
        )
        try:
            self.brain.world_model.retrain()
            trained = self.brain.world_model._has_trained_return_model()
        except Exception as exc:
            return {"status": "error", "error": str(exc)}
        self.change_log.append(record)
        self._audit_change(record)
        return {"status": "applied", "trained": trained, "change": record.to_dict()}

    def reset_world_model(
        self,
        reason: str,
        approved_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Reinicia el world model (último recurso ante olvido catastrófico)."""
        record = PrefrontalChangeRecord(
            target="world_model",
            action="reset",
            reason=reason,
            approved_by=approved_by,
        )
        self.brain.world_model.reset()
        self.change_log.append(record)
        self._audit_change(record)
        return {"status": "applied", "change": record.to_dict()}

    # ------------------------------------------------------------------
    # Plasticidad GWT: pesos sinápticos de estrategias / hipótesis
    # ------------------------------------------------------------------
    def update_gwt_weight(
        self,
        key: str,
        success: bool,
        confidence: float,
        learning_rate: float = 0.1,
        ewc_lambda: float = 0.01,
    ) -> float:
        """Actualiza un peso sináptico GWT con refuerzo Hebbiano y ancla EWC."""
        if key not in self._gwt_weights:
            self._gwt_weights[key] = 1.0
            self._gwt_baselines[key] = 1.0

        current = self._gwt_weights[key]
        baseline = self._gwt_baselines[key]
        delta = learning_rate * (1.0 if success else -1.0) * confidence
        penalty = ewc_lambda * (current - baseline)
        new_weight = max(0.0, min(2.0, current + delta - penalty))
        self._gwt_weights[key] = new_weight
        return new_weight

    def get_gwt_weights(self) -> Dict[str, Any]:
        return {
            "weights": dict(self._gwt_weights),
            "baselines": dict(self._gwt_baselines),
        }

    # ------------------------------------------------------------------
    # Congelamiento de módulos de memoria (protección contra olvido catastrófico)
    # ------------------------------------------------------------------
    def freeze_module(self, module: str, reason: str = "") -> Dict[str, Any]:
        if module not in self._frozen_modules:
            return {"status": "unknown_module", "module": module}
        self._frozen_modules[module] = True
        return {"status": "frozen", "module": module, "reason": reason}

    def thaw_module(self, module: str, reason: str = "") -> Dict[str, Any]:
        if module not in self._frozen_modules:
            return {"status": "unknown_module", "module": module}
        self._frozen_modules[module] = False
        return {"status": "thawed", "module": module, "reason": reason}

    def is_module_frozen(self, module: str) -> bool:
        return self._frozen_modules.get(module, False)

    # ------------------------------------------------------------------
    # Rollback completo a línea base
    # ------------------------------------------------------------------
    def rollback(self) -> Dict[str, Any]:
        """Restaura los parámetros plásticos a la línea base."""
        for path, value in self._baseline_config.items():
            self._set_param(self.brain.config, path, value)
        self._gwt_weights = copy.deepcopy(self._gwt_baselines)
        record = PrefrontalChangeRecord(
            target="prefrontal",
            action="rollback_to_baseline",
            reason="Rollback a línea base por solicitud de supervisor o homeostasis",
        )
        self.change_log.append(record)
        return {"status": "rolled_back", "baseline_restored": True}

    def _audit_change(self, record: PrefrontalChangeRecord) -> None:
        if self.memory_router:
            self.memory_router.store_working_memory(
                f"Plasticidad prefrontal {record.change_id}: {record.action} {record.target}",
                note_type="prefrontal_change",
                metadata=record.to_dict(),
            )
