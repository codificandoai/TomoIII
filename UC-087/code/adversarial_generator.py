"""
UC-087 — Generador de ejemplos adversarios y triggers.

Implementa FGSM, PGD y triggers de backdoor simples para datos tabulares,
sin dependencias externas. Funciona con cualquier modelo que exponga
predict_proba y gradiente numérico o una función de pérdida.
"""

import copy
import random
from typing import List, Callable, Optional, Tuple, Dict, Any

from models_087 import DataPoint


class AdversarialGenerator:
    """
    Genera perturbaciones adversarias para datos tabulares usando FGSM y PGD.
    También inyecta triggers de backdoor para evaluación de robustez.
    """

    def __init__(self, epsilon: float = 0.05, steps: int = 10, step_size: float = 0.01):
        self.epsilon = epsilon
        self.steps = steps
        self.step_size = step_size

    def _loss(self, model_fn: Callable[[List[float]], float], features: List[float], target: int) -> float:
        """Pérdida binaria simplificada: -log(p[target])."""
        prob = model_fn(features)
        p = max(prob, 1e-9) if target == 1 else max(1.0 - prob, 1e-9)
        return -math.log(p)

    def _numeric_gradient(
        self,
        model_fn: Callable[[List[float]], float],
        features: List[float],
        target: int,
        delta: float = 1e-4,
    ) -> List[float]:
        """Calcula gradiente numérico de la pérdida respecto a features."""
        grad = []
        base_loss = self._loss(model_fn, features, target)
        for i in range(len(features)):
            perturbed = features[:]
            perturbed[i] += delta
            loss_perturbed = self._loss(model_fn, perturbed, target)
            grad.append((loss_perturbed - base_loss) / delta)
        return grad

    def fgsm(self, features: List[float], gradient: List[float]) -> List[float]:
        """Fast Gradient Sign Method."""
        return [features[i] + self.epsilon * math.copysign(1.0, gradient[i]) for i in range(len(features))]

    def pgd(
        self,
        model_fn: Callable[[List[float]], float],
        features: List[float],
        target: int,
    ) -> List[float]:
        """Projected Gradient Descent básico con clip a L-inf epsilon."""
        current = features[:]
        for _ in range(self.steps):
            grad = self._numeric_gradient(model_fn, current, target)
            for i in range(len(current)):
                current[i] += self.step_size * math.copysign(1.0, grad[i])
                # Proyección L-inf
                diff = current[i] - features[i]
                diff = max(-self.epsilon, min(self.epsilon, diff))
                current[i] = features[i] + diff
        return current

    def generate_adversarial_point(
        self,
        dp: DataPoint,
        model_fn: Callable[[List[float]], float],
        attack: str = "pgd",
    ) -> DataPoint:
        """Genera un punto adversario a partir de uno limpio."""
        if attack == "fgsm":
            grad = self._numeric_gradient(model_fn, dp.features, dp.label or 0)
            adv_features = self.fgsm(dp.features, grad)
        else:
            adv_features = self.pgd(model_fn, dp.features, dp.label or 0)
        return DataPoint(
            features=adv_features,
            label=dp.label,
            metadata={"adversarial": True, "original": dp.features, "attack": attack},
        )

    def generate_batch(
        self,
        data: List[DataPoint],
        model_fn: Callable[[List[float]], float],
        attack: str = "pgd",
        fraction: float = 1.0,
    ) -> List[DataPoint]:
        """Genera ejemplos adversarios para una fracción del batch."""
        selected = data if fraction >= 1.0 else random.sample(data, max(1, int(len(data) * fraction)))
        return [self.generate_adversarial_point(dp, model_fn, attack) for dp in selected]

    def inject_backdoor_trigger(
        self,
        data: List[DataPoint],
        trigger_value: float = 9.5,
        feature_index: int = 0,
        target_label: int = 1,
        fraction: float = 0.1,
    ) -> Tuple[List[DataPoint], List[int]]:
        """
        Inyecta un trigger simple en una fracción del dataset y cambia su
label a target_label. Retorna datos envenenados e índices afectados.
        """
        poisoned = [copy.deepcopy(dp) for dp in data]
        n = int(len(poisoned) * fraction)
        indices = random.sample(range(len(poisoned)), n)
        for idx in indices:
            poisoned[idx].features[feature_index] = trigger_value
            poisoned[idx].label = target_label
            poisoned[idx].metadata["trigger"] = True
            poisoned[idx].metadata["trigger_feature"] = feature_index
        return poisoned, indices

    def generate_triggers_for_testing(
        self,
        feature_dim: int,
        n_triggers: int = 5,
    ) -> List[Dict[str, Any]]:
        """Genera configuraciones de triggers para red teaming."""
        triggers = []
        for i in range(n_triggers):
            triggers.append({
                "trigger_id": f"trigger_{i+1}",
                "feature_index": i % feature_dim,
                "trigger_value": round(8.0 + i * 0.5, 2),
                "target_label": (i + 1) % 2,
            })
        return triggers


import math  # noqa: E402
