"""
UC-087 — Evaluador de robustez adversaria y red teaming.

Calcula accuracy limpia vs. accuracy adversarial y rechaza modelos cuya
brecha de robustez supere el umbral configurado.
"""

import math
from typing import List, Dict, Any, Callable

from models_087 import DataPoint, RobustnessReport
from adversarial_generator import AdversarialGenerator


class RobustnessEvaluator:
    """
    Ejecuta pruebas de robustez con ejemplos adversarios generados (FGSM, PGD)
y evalúa si un modelo es lo suficientemente robusto para ser promocionado.
    """

    def __init__(self, generator: AdversarialGenerator, robustness_gap_threshold: float = 0.15):
        self.generator = generator
        self.robustness_gap_threshold = robustness_gap_threshold

    def _predict_fn(self, model: Any, features: List[float]) -> float:
        """Predice probabilidad positiva para un punto."""
        if hasattr(model, "predict_proba"):
            proba = model.predict_proba(features)
            if isinstance(proba, (list, tuple)):
                return float(proba[1]) if len(proba) > 1 else float(proba[0])
            return float(proba)
        if hasattr(model, "predict"):
            return float(model.predict(features))
        return float(model(features))

    def evaluate(
        self,
        model: Any,
        clean_data: List[DataPoint],
        attack: str = "pgd",
    ) -> RobustnessReport:
        """Evalúa robustez generando adversariales y comparando accuracies."""
        predict_fn = lambda f: self._predict_fn(model, f)

        clean_acc = self._accuracy(model, clean_data)
        adversarial = self.generator.generate_batch(clean_data, predict_fn, attack=attack)
        adv_acc = self._accuracy(model, adversarial)

        gap = clean_acc - adv_acc
        passed = gap <= self.robustness_gap_threshold

        return RobustnessReport(
            clean_accuracy=clean_acc,
            adversarial_accuracy=adv_acc,
            robustness_gap=gap,
            passed=passed,
            attack_type=attack,
            details={
                "n_clean": len(clean_data),
                "n_adversarial": len(adversarial),
                "threshold": self.robustness_gap_threshold,
            },
        )

    def _accuracy(self, model: Any, data: List[DataPoint]) -> float:
        if not data:
            return 0.0
        correct = 0
        total = 0
        for dp in data:
            if dp.label is None:
                continue
            pred = self._predict_label(model, dp.features)
            if pred == dp.label:
                correct += 1
            total += 1
        return correct / total if total > 0 else 0.0

    def _predict_label(self, model: Any, features: List[float]) -> int:
        if hasattr(model, "predict"):
            pred = model.predict(features)
            if isinstance(pred, (list, tuple)):
                return int(pred[0])
            return int(pred)
        proba = self._predict_fn(model, features)
        return 1 if proba >= 0.5 else 0

    def red_team_report(
        self,
        model: Any,
        clean_data: List[DataPoint],
        attacks: List[str] = None,
    ) -> Dict[str, Any]:
        """Ejecuta múltiples ataques y reporta el peor caso."""
        attacks = attacks or ["fgsm", "pgd"]
        reports = {}
        worst = None
        for attack in attacks:
            report = self.evaluate(model, clean_data, attack=attack)
            reports[attack] = report.to_dict()
            if worst is None or report.robustness_gap > worst.robustness_gap:
                worst = report
        return {
            "reports": reports,
            "worst_attack": worst.attack_type if worst else None,
            "worst_gap": worst.robustness_gap if worst else 0.0,
            "passed_all": all(r["passed"] for r in reports.values()),
        }

    def entropy_of_predictions(self, model: Any, data: List[DataPoint]) -> float:
        """Calcula entropía media de las predicciones del modelo."""
        if not data:
            return 0.0
        total_entropy = 0.0
        n = 0
        for dp in data:
            p = self._predict_fn(model, dp.features)
            p = max(1e-9, min(1.0 - 1e-9, p))
            total_entropy += -(p * math.log(p) + (1 - p) * math.log(1 - p))
            n += 1
        return total_entropy / n if n > 0 else 0.0


class AnyModel:
    """Dummy placeholder for type hints."""
    pass
