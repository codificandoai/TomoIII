"""Persistencia de modelos probabilísticos entrenados para UC-266.

Guarda y carga modelos PyTorch (`state_dict`) y el dataset de experiencias.
En producción se puede adaptar a ONNX, MLflow, etc.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import numpy as np

from probabilistic_model import GPTransitionModel, NeuralTransitionModel


try:
    import torch
    _TORCH_AVAILABLE = True
except Exception:  # pragma: no cover
    _TORCH_AVAILABLE = False


@dataclass
class SavedModels:
    neural_success: Optional[Any] = None
    neural_reward: Optional[Any] = None
    gp_X: Optional[Any] = None
    gp_y: Optional[Any] = None
    metadata: Dict[str, Any] | None = None


class ModelPersistence:
    """Guarda y carga modelos entrenados en disco."""

    DEFAULT_DIR = os.path.join(os.path.dirname(__file__), "models")

    def __init__(self, output_dir: Optional[str] = None) -> None:
        self.output_dir = output_dir or self.DEFAULT_DIR
        os.makedirs(self.output_dir, exist_ok=True)

    def paths(self) -> Dict[str, str]:
        return {
            "neural_success": os.path.join(self.output_dir, "neural_success_model.pt"),
            "neural_reward": os.path.join(self.output_dir, "neural_reward_model.pt"),
            "neural_params": os.path.join(self.output_dir, "neural_params.json"),
            "gp_state": os.path.join(self.output_dir, "gp_state.npz"),
            "experiences": os.path.join(self.output_dir, "experiences.npz"),
            "metadata": os.path.join(self.output_dir, "model_metadata.json"),
        }

    def save(
        self,
        neural_model: Optional[NeuralTransitionModel] = None,
        gp_model: Optional[GPTransitionModel] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """Guarda los modelos entrenados."""
        paths = self.paths()
        saved: Dict[str, str] = {}
        if neural_model and neural_model._trained and _TORCH_AVAILABLE:
            torch.save(neural_model.model_success.state_dict(), paths["neural_success"])
            torch.save(neural_model.model_reward.state_dict(), paths["neural_reward"])
            params = {
                "input_dim": int(neural_model.model_success.net[0].in_features),
                "hidden_dim": int(neural_model.model_success.net[0].out_features),
                "dropout": neural_model.config.torch.dropout,
                "device": str(neural_model.device),
            }
            with open(paths["neural_params"], "w", encoding="utf-8") as f:
                json.dump(params, f, ensure_ascii=False)
            saved["neural_success"] = paths["neural_success"]
            saved["neural_reward"] = paths["neural_reward"]
            saved["neural_params"] = paths["neural_params"]
            if neural_model._X:
                np.savez(
                    paths["experiences"],
                    X=np.array(neural_model._X),
                    y_success=np.array(neural_model._y_success),
                    y_reward=np.array(neural_model._y_reward),
                )
                saved["experiences"] = paths["experiences"]

        if gp_model and gp_model._trained:
            np.savez(
                paths["gp_state"],
                X=gp_model._X,
                y=gp_model._y,
            )
            saved["gp_state"] = paths["gp_state"]

        meta = metadata or {}
        meta["saved_files"] = list(saved.keys())
        with open(paths["metadata"], "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        saved["metadata"] = paths["metadata"]
        return saved

    def load(self) -> SavedModels:
        """Carga modelos previamente guardados."""
        paths = self.paths()
        loaded = SavedModels()
        if _TORCH_AVAILABLE and os.path.exists(paths["neural_success"]):
            loaded.neural_success = torch.load(
                paths["neural_success"], map_location="cpu", weights_only=True
            )
        if _TORCH_AVAILABLE and os.path.exists(paths["neural_reward"]):
            loaded.neural_reward = torch.load(
                paths["neural_reward"], map_location="cpu", weights_only=True
            )
        if os.path.exists(paths["neural_params"]):
            loaded.metadata = json.load(open(paths["neural_params"], "r", encoding="utf-8"))
        if os.path.exists(paths["gp_state"]):
            data = np.load(paths["gp_state"], allow_pickle=True)
            loaded.gp_X = list(data["X"])
            loaded.gp_y = list(data["y"])
        if os.path.exists(paths["metadata"]):
            with open(paths["metadata"], "r", encoding="utf-8") as f:
                meta = json.load(f)
            loaded.metadata = {**(loaded.metadata or {}), **meta}
        return loaded

    def attach_to_world_model(
        self, world_model: Any
    ) -> Tuple[bool, bool]:
        """Carga modelos guardados y los asigna a un TravelWorldModel."""
        loaded = self.load()
        attached_neural = False
        attached_gp = False
        if _TORCH_AVAILABLE and isinstance(world_model.probabilistic_model, NeuralTransitionModel):
            if loaded.neural_success and loaded.neural_reward:
                world_model.probabilistic_model.model_success.load_state_dict(
                    loaded.neural_success
                )
                world_model.probabilistic_model.model_reward.load_state_dict(
                    loaded.neural_reward
                )
                world_model.probabilistic_model.model_success.eval()
                world_model.probabilistic_model.model_reward.eval()
                world_model.probabilistic_model._trained = True
                attached_neural = True
        if isinstance(world_model.probabilistic_model, GPTransitionModel):
            if loaded.gp_X is not None and loaded.gp_y is not None:
                world_model.probabilistic_model._X = loaded.gp_X
                world_model.probabilistic_model._y = loaded.gp_y
                world_model.probabilistic_model.fit()
                attached_gp = True
        return attached_neural, attached_gp

    def exists(self) -> bool:
        paths = self.paths()
        return os.path.exists(paths["metadata"]) and (
            os.path.exists(paths["neural_success"]) or os.path.exists(paths["gp_state"])
        )
