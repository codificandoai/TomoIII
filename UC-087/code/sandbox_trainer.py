"""
UC-087 — Entrenamiento en sandbox con adversarial augmentation.

Entrena modelos candidatos en un entorno aislado, inyectando ejemplos
adversarios generados para mejorar robustez antes de promoción.
"""

import copy
from typing import List, Dict, Any

from models_087 import DataPoint, MLSecOpsConfig
from adversarial_generator import AdversarialGenerator
from sandbox_model import SandboxLogisticModel


class SandboxTrainer:
    """
    Entrena un modelo candidato en sandbox:
    1. Entrena con datos limpios filtrados.
    2. Genera adversariales.
    3. Reentrena con datos + adversariales.
    4. Retorna modelo candidato sin modificar el modelo de producción.
    """

    def __init__(
        self,
        config: MLSecOpsConfig,
        adversarial_generator: AdversarialGenerator,
        base_model: SandboxLogisticModel = None,
    ):
        self.config = config
        self.generator = adversarial_generator
        self.base_model = base_model or SandboxLogisticModel()

    def train(
        self,
        clean_data: List[DataPoint],
        adversarial_fraction: float = 0.5,
        attack: str = "pgd",
    ) -> SandboxLogisticModel:
        """Entrena un modelo con datos limpios + adversariales en sandbox."""
        if len(clean_data) < self.config.min_samples_for_training:
            raise ValueError(f"Insuficientes datos: {len(clean_data)} < {self.config.min_samples_for_training}")

        # 1. Entrenar modelo base
        candidate = copy.deepcopy(self.base_model)
        dim = len(clean_data[0].features)
        if candidate.dim is None:
            candidate.dim = dim
            candidate.weights = [__import__("random").uniform(-0.1, 0.1) for _ in range(dim)]
        candidate.fit(clean_data)

        # 2. Generar adversariales usando el propio candidato
        predict_fn = lambda f: candidate.predict_proba(f)
        adversarials = self.generator.generate_batch(
            clean_data,
            predict_fn,
            attack=attack,
            fraction=adversarial_fraction,
        )

        # 3. Reentrenar con datos mixtos
        mixed = clean_data + adversarials
        candidate.fit(mixed)

        return candidate

    def cross_validate_robustness(
        self,
        model: SandboxLogisticModel,
        clean_data: List[DataPoint],
        attacks: List[str],
    ) -> Dict[str, Any]:
        """Evalúa robustez del candidato contra varios ataques."""
        from robustness_evaluator import RobustnessEvaluator
        evaluator = RobustnessEvaluator(self.generator, self.config.robustness_gap_threshold)
        return evaluator.red_team_report(model, clean_data, attacks=attacks)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "config": self.config.to_dict(),
            "base_model_trained": self.base_model.trained,
        }
