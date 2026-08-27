"""Persistencia de modelos probabilísticos entrenados para UC-265.

Guarda y carga los modelos scikit-learn (MLPRegressor y GaussianProcessRegressor)
usando joblib. En producción se puede adaptar a ONNX, MLflow, etc.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from probabilistic_model import GPTransitionModel, NeuralTransitionModel


try:
    import joblib
except ImportError:  # pragma: no cover - fallback por si joblib no está instalado
    joblib = None  # type: ignore


@dataclass
class SavedModels:
    neural_success: Optional[Any] = None
    neural_reward: Optional[Any] = None
    gp_model: Optional[Any] = None
    metadata: Dict[str, Any] | None = None


class ModelPersistence:
    """Guarda y carga modelos entrenados en disco."""

    DEFAULT_DIR = os.path.join(os.path.dirname(__file__), "models")

    def __init__(self, output_dir: Optional[str] = None) -> None:
        self.output_dir = output_dir or self.DEFAULT_DIR
        os.makedirs(self.output_dir, exist_ok=True)

    def paths(self) -> Dict[str, str]:
        return {
            "neural_success": os.path.join(self.output_dir, "neural_success_model.joblib"),
            "neural_reward": os.path.join(self.output_dir, "neural_reward_model.joblib"),
            "gp": os.path.join(self.output_dir, "gp_model.joblib"),
            "metadata": os.path.join(self.output_dir, "model_metadata.json"),
        }

    def save(
        self,
        neural_model: Optional[NeuralTransitionModel] = None,
        gp_model: Optional[GPTransitionModel] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """Guarda los modelos entrenados."""
        if joblib is None:
            raise RuntimeError("joblib no está instalado. Ejecuta: pip install joblib")
        paths = self.paths()
        saved: Dict[str, str] = {}
        if neural_model and neural_model._trained:
            joblib.dump(neural_model.model_success, paths["neural_success"])
            joblib.dump(neural_model.model_reward, paths["neural_reward"])
            saved["neural_success"] = paths["neural_success"]
            saved["neural_reward"] = paths["neural_reward"]
        if gp_model and gp_model._trained:
            joblib.dump(gp_model.model, paths["gp"])
            saved["gp"] = paths["gp"]
        meta = metadata or {}
        meta["saved_files"] = list(saved.keys())
        with open(paths["metadata"], "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        saved["metadata"] = paths["metadata"]
        return saved

    def load(self) -> SavedModels:
        """Carga modelos previamente guardados."""
        if joblib is None:
            raise RuntimeError("joblib no está instalado")
        paths = self.paths()
        loaded = SavedModels()
        if os.path.exists(paths["neural_success"]):
            loaded.neural_success = joblib.load(paths["neural_success"])
        if os.path.exists(paths["neural_reward"]):
            loaded.neural_reward = joblib.load(paths["neural_reward"])
        if os.path.exists(paths["gp"]):
            loaded.gp_model = joblib.load(paths["gp"])
        if os.path.exists(paths["metadata"]):
            with open(paths["metadata"], "r", encoding="utf-8") as f:
                loaded.metadata = json.load(f)
        return loaded

    def attach_to_world_model(
        self, world_model: Any
    ) -> Tuple[bool, bool]:
        """Carga modelos guardados y los asigna a un TravelWorldModel."""
        loaded = self.load()
        attached_neural = False
        attached_gp = False
        if (
            loaded.neural_success
            and loaded.neural_reward
            and isinstance(world_model.probabilistic_model, NeuralTransitionModel)
        ):
            world_model.probabilistic_model.model_success = loaded.neural_success
            world_model.probabilistic_model.model_reward = loaded.neural_reward
            world_model.probabilistic_model._trained = True
            attached_neural = True
        if (
            loaded.gp_model
            and isinstance(world_model.probabilistic_model, GPTransitionModel)
        ):
            world_model.probabilistic_model.model = loaded.gp_model
            world_model.probabilistic_model._trained = True
            attached_gp = True
        return attached_neural, attached_gp

    def exists(self) -> bool:
        paths = self.paths()
        return os.path.exists(paths["metadata"]) and (
            os.path.exists(paths["neural_success"]) or os.path.exists(paths["gp"])
        )
