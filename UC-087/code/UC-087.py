"""
Codificando.AI
UC-087: MLSecOps / Defense in Depth para proteger modelos AGI de UC-315.

Capa externa de seguridad del ciclo de vida del modelo. Protege
TradingWorldModel, NeuralTransitionModel y GPTransitionModel mediante
validación de provenance, filtrado de entradas, entrenamiento adversario,
red teaming, detección de backdoors, sandbox, rollback y escalación.

Products:
- bloower.com: AI-Native Platform.
- c4ml.io: Infrastructure as Code.
- analitycsdata.com: etl(batch-online-offline).
- cloudatasecure.com: vault.
- qbex.ai: AI-Native Cost & Migrations Operations.
- utron.ai: AI-Solutions ready for you.
- trackpro.ai: AI-Native Projects Ready to deploy.
"""

import random
from typing import List, Dict, Any, Optional

from models_087 import MLSecOpsConfig, DataPoint
from model_guardian import ModelSecurityGuardian


class UCMLSecOpsLayer:
    """Wrapper de alto nivel para UC-087."""

    def __init__(self, config: Optional[MLSecOpsConfig] = None):
        self.guardian = ModelSecurityGuardian(config=config)

    def validate_batch(
        self,
        data: List[Dict[str, Any]],
        expected_hash: Optional[str] = None,
        signature: Optional[Dict[str, str]] = None,
        source: str = "unknown",
        allowed_sources: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        points = self._to_points(data)
        report = self.guardian.validate_and_sanitize(
            points, expected_hash, signature, source, allowed_sources
        )
        return report.to_dict()

    def train_candidate(self, data: List[Dict[str, Any]], attack: str = "pgd") -> Dict[str, Any]:
        points = self._to_points(data)
        candidate = self.guardian.train_candidate(points, attack=attack)
        return {
            "trained": candidate.trained,
            "dim": candidate.dim,
            "weights_sample": candidate.weights[:3] if candidate.weights else [],
        }

    def evaluate_robustness(
        self,
        data: List[Dict[str, Any]],
        attack: str = "pgd",
    ) -> Dict[str, Any]:
        points = self._to_points(data)
        candidate = self.guardian.train_candidate(points, attack=attack)
        report = self.guardian.evaluate_robustness(candidate, points, attacks=[attack])
        return report.to_dict()

    def detect_backdoors(
        self,
        data: List[Dict[str, Any]],
        baseline_metrics: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        points = self._to_points(data)
        candidate = self.guardian.train_candidate(points)
        baseline = baseline_metrics or {"entropy": 0.5, "trigger_slice_acc": 0.85}
        report = self.guardian.detect_backdoors(candidate, points, baseline)
        return report.to_dict()

    def process_batch(
        self,
        data: List[Dict[str, Any]],
        expected_hash: Optional[str] = None,
        signature: Optional[Dict[str, str]] = None,
        source: str = "unknown",
        allowed_sources: Optional[List[str]] = None,
        baseline_metrics: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        points = self._to_points(data)
        result = self.guardian.process_training_batch(
            points,
            expected_hash,
            signature,
            source,
            allowed_sources,
            baseline_metrics,
        )
        return result.to_dict()

    def approve_canary(self, version_id: str) -> Dict[str, Any]:
        promoted = self.guardian.approve_canary(version_id)
        return promoted or {"status": "not_found"}

    def rollback(self, version_id: Optional[str] = None) -> Dict[str, Any]:
        result = self.guardian.rollback(version_id)
        return result or {"status": "no_safe_version"}

    def status(self) -> Dict[str, Any]:
        return self.guardian.get_status()

    def reset(self) -> None:
        self.guardian = ModelSecurityGuardian(config=self.guardian.config)

    @staticmethod
    def _to_points(data: List[Dict[str, Any]]) -> List[DataPoint]:
        return [
            DataPoint(
                features=item.get("features", []),
                label=item.get("label"),
                metadata=item.get("metadata", {}),
            )
            for item in data
        ]


def _generate_clean_data(n: int = 200, dim: int = 4, seed: int = 42) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    data = []
    for i in range(n):
        features = [rng.gauss(0, 1) for _ in range(dim)]
        label = 1 if sum(features[:2]) > 0 else 0
        data.append({"features": features, "label": label})
    return data


def _inject_backdoor(data: List[Dict[str, Any]], fraction: float = 0.35, trigger_value: float = 2.0) -> List[Dict[str, Any]]:
    import copy
    poisoned = copy.deepcopy(data)
    n = int(len(poisoned) * fraction)
    for item in poisoned[:n]:
        item["features"][0] = trigger_value
        item["label"] = 0  # label invertido -> activa backdoor
        item["metadata"] = {"trigger": True}
    return poisoned


def demo() -> None:
    print("=" * 80)
    print("UC-087 — MLSecOps / Defense in Depth")
    print("=" * 80)

    layer = UCMLSecOpsLayer(config=MLSecOpsConfig(
        robustness_gap_threshold=0.25,
        slice_drop_threshold=0.20,
        entropy_anomaly_zscore=10.0,
    ))

    clean_data = _generate_clean_data(200, 4)

    print("\n1. Procesando batch limpio...")
    result_clean = layer.process_batch(
        clean_data,
        source="trusted_pipeline",
        allowed_sources=["trusted_pipeline"],
        baseline_metrics={"entropy": 0.7, "trigger_slice_acc": 0.95},
    )
    print(f"   Decisión: {result_clean['decision']['action']}")
    print(f"   Promoción: {result_clean['decision']['promotion']}")
    print(f"   Robust gap: {result_clean['decision']['robustness_report']['robustness_gap']:.2%}")

    print("\n2. Procesando batch con backdoor...")
    poisoned_data = _inject_backdoor(clean_data, fraction=0.15)
    result_poison = layer.process_batch(
        poisoned_data,
        source="trusted_pipeline",
        allowed_sources=["trusted_pipeline"],
        baseline_metrics={"entropy": 0.7, "trigger_slice_acc": 0.95},
    )
    print(f"   Decisión: {result_poison['decision']['action']}")
    print(f"   Promoción: {result_poison['decision']['promotion']}")
    print(f"   Categorías amenaza: {result_poison['decision']['threat_categories']}")
    print(f"   Slice alerts: {len(result_poison['decision']['trigger_report']['slice_alerts'])}")

    print("\n3. Estado del guardian...")
    status = layer.status()
    print(f"   Versiones: {status['versions'][-1] if status['versions'] else 'N/A'}")
    print(f"   Alertas: {status['alerts']}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    demo()
