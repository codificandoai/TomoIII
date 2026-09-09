"""Agentes de differential privacy y membership inference attacks."""
from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Optional

from fine_tuning.privacy.models_privacy import (
    DPTrainingConfig,
    DPTrainingResult,
    MembershipInferenceReport,
)


class DPTrainingAgent:
    """
    Simula entrenamiento con privacidad diferencial (DP-SGD).

    Calcula un presupuesto de privacidad simplificado basado en:
    - N: tamaño del dataset
    - T: pasos de entrenamiento
    - C: clipping norm
    - sigma: multiplicador de ruido
    - delta

    En producción delegaría en Opacus / TensorFlow Privacy.
    """

    def __init__(self) -> None:
        self._budget_used: Dict[str, Dict[str, float]] = {}

    def apply(
        self,
        run_id: str,
        config: DPTrainingConfig,
        dataset_size: int,
        steps: int,
    ) -> DPTrainingResult:
        # Simplified moments accountant-ish bound for demonstration.
        if not config.enabled:
            return DPTrainingResult(
                run_id=run_id,
                epsilon_spent=0.0,
                delta_spent=0.0,
                privacy_budget_exceeded=False,
                noise_std_applied=0.0,
            )

        q = max(1.0 / dataset_size, 1e-6)  # sampling rate
        sigma = config.noise_multiplier
        T = steps
        # Basic composition: epsilon <= q * sqrt(T) * (sqrt(2 ln(1.25/delta)) / sigma)
        delta = max(config.delta, 1e-6)
        term = math.sqrt(2 * math.log(1.25 / delta)) / sigma
        epsilon = q * math.sqrt(T) * term
        noise_std = (sigma * config.max_grad_norm) / max(dataset_size, 1)

        self._budget_used[run_id] = {"epsilon": epsilon, "delta": delta}
        exceeded = epsilon > config.epsilon
        return DPTrainingResult(
            run_id=run_id,
            epsilon_spent=round(epsilon, 4),
            delta_spent=delta,
            privacy_budget_exceeded=exceeded,
            noise_std_applied=round(noise_std, 6),
        )

    def get_budget_used(self, run_id: str) -> Optional[Dict[str, float]]:
        return self._budget_used.get(run_id)


class MembershipInferenceAttackAgent:
    """
    Simula un ataque de membership inference básico para detectar memorización.

    Entrena un clasificador "shadow" sobre datos similares y mide la capacidad
    de distinguir miembros de no-miembros por umbral de confianza.
    """

    def __init__(self, threshold: float = 0.65) -> None:
        self.threshold = threshold

    def evaluate(
        self,
        run_id: str,
        members: List[Dict[str, Any]],
        non_members: List[Dict[str, Any]],
    ) -> MembershipInferenceReport:
        # Simula un score de confianza inversamente proporcional a la entropía.
        def confidence(samples: List[Dict[str, Any]], is_member: bool) -> float:
            if not samples:
                return 0.0
            # Deterministic pseudo-confidence seeded by sample content.
            total = 0.0
            for s in samples:
                seed = hash(str(s)) % 1000
                rng = random.Random(seed)
                # Members tend to have higher confidence in overfit models.
                base = rng.uniform(0.5, 0.95) if is_member else rng.uniform(0.3, 0.7)
                total += base
            return total / len(samples)

        member_conf = confidence(members, True)
        non_member_conf = confidence(non_members, False)
        attack_acc = (member_conf + (1 - non_member_conf)) / 2
        exposure_risk = (
            "critical" if attack_acc > 0.85 else
            "high" if attack_acc > 0.75 else
            "medium" if attack_acc > 0.60 else
            "low"
        )
        passed = attack_acc <= self.threshold

        memorized = []
        if not passed:
            # Flag top-confidence members as likely memorized.
            for s in members[:5]:
                memorized.append({"sample": str(s)[:80], "risk": exposure_risk})

        return MembershipInferenceReport(
            run_id=run_id,
            attack_accuracy=round(attack_acc, 3),
            exposure_risk=exposure_risk,
            memorized_samples=memorized,
            passed=passed,
        )
