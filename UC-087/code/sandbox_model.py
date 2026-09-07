"""
UC-087 — Modelo de referencia en sandbox para entrenamiento y robustez.

Implementa una regresión logística simple con numpy puro para poder
entrenar, evaluar y generar adversariales sin dependencias pesadas.
Sirve como proxy de NeuralTransitionModel / GPTransitionModel de UC-315.
"""

import math
import random
from typing import List, Tuple, Optional, Dict, Any

from models_087 import DataPoint


class SandboxLogisticModel:
    """
    Modelo lineal binario con activación sigmoide y entrenamiento por SGD.

    Exponen la interfaz mínima que espera el guardian:
    - fit(X, y)
    - predict(features) -> int
    - predict_proba(features) -> float
    - evaluate(data) -> accuracy
    - to_dict() / from_dict()
    """

    def __init__(self, dim: Optional[int] = None, lr: float = 0.01, epochs: int = 100):
        self.dim = dim
        self.lr = lr
        self.epochs = epochs
        self.weights: List[float] = []
        self.bias: float = 0.0
        self.trained: bool = False
        if dim is not None:
            self.weights = [random.uniform(-0.1, 0.1) for _ in range(dim)]

    def _sigmoid(self, z: float) -> float:
        if z >= 0:
            return 1.0 / (1.0 + math.exp(-z))
        exp_z = math.exp(z)
        return exp_z / (1.0 + exp_z)

    def _logit(self, features: List[float]) -> float:
        return sum(w * f for w, f in zip(self.weights, features)) + self.bias

    def predict_proba(self, features: List[float]) -> float:
        return self._sigmoid(self._logit(features))

    def predict(self, features: List[float]) -> int:
        return 1 if self.predict_proba(features) >= 0.5 else 0

    def _clip(self, value: float) -> float:
        return max(1e-9, min(1.0 - 1e-9, value))

    def fit(self, data: List[DataPoint]) -> "SandboxLogisticModel":
        if not data:
            return self
        self.dim = len(data[0].features)
        if not self.weights:
            self.weights = [random.uniform(-0.1, 0.1) for _ in range(self.dim)]

        for _ in range(self.epochs):
            total_dw = [0.0] * self.dim
            total_db = 0.0
            n = 0
            for dp in data:
                if dp.label is None:
                    continue
                y = dp.label
                p = self._clip(self.predict_proba(dp.features))
                error = p - y
                for j in range(self.dim):
                    total_dw[j] += error * dp.features[j]
                total_db += error
                n += 1
            if n == 0:
                continue
            for j in range(self.dim):
                self.weights[j] -= self.lr * total_dw[j] / n
            self.bias -= self.lr * total_db / n
        self.trained = True
        return self

    def evaluate(self, data: List[DataPoint]) -> float:
        if not data:
            return 0.0
        correct = 0
        total = 0
        for dp in data:
            if dp.label is None:
                continue
            pred = self.predict(dp.features)
            if pred == dp.label:
                correct += 1
            total += 1
        return correct / total if total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "weights": self.weights,
            "bias": self.bias,
            "dim": self.dim,
            "trained": self.trained,
        }

    def from_dict(self, state: Dict[str, Any]) -> "SandboxLogisticModel":
        self.weights = state.get("weights", [])
        self.bias = state.get("bias", 0.0)
        self.dim = state.get("dim", None)
        self.trained = state.get("trained", False)
        return self

    def __call__(self, features: List[float]) -> int:
        return self.predict(features)


class ModelWrapper:
    """Adaptador para modelos externos que no implementan predict_proba."""

    def __init__(self, model: Any):
        self.model = model
        self.has_proba = hasattr(model, "predict_proba")

    def predict(self, features: List[float]) -> int:
        if hasattr(self.model, "predict"):
            return int(self.model.predict([features])[0])
        return int(self.model(features))

    def predict_proba(self, features: List[float]) -> float:
        if self.has_proba:
            proba = self.model.predict_proba([features])[0]
            if isinstance(proba, (list, tuple)):
                return float(proba[1]) if len(proba) > 1 else float(proba[0])
            return float(proba)
        pred = self.predict(features)
        return 0.9 if pred == 1 else 0.1
