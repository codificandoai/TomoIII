"""UC-703 fine_tuning — Despliegue, canary, drift/alucinaciones y feedback loop."""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from fine_tuning.models_ft import ClosedLoopCycle, Deployment, DriftReport, FeedbackItem, ModelBundle


class DeploymentAgent:
    """
    Crea bundles atómicos base+adapter+prompt+params y decide modo de serving.
    """

    def __init__(self) -> None:
        self._deployments: Dict[str, Deployment] = {}

    def build_bundle(
        self,
        base_model: str,
        adapter_uri: str,
        prompt_template: str,
        generation_params: Dict[str, Any],
        dataset_version_id: str,
        training_run_id: str,
    ) -> ModelBundle:
        bundle = ModelBundle(
            base_model=base_model,
            adapter_uri=adapter_uri,
            prompt_template=prompt_template,
            generation_params=generation_params,
            dataset_version_id=dataset_version_id,
            training_run_id=training_run_id,
        )
        payload = bundle.to_dict()
        payload.pop("bundle_id")
        payload.pop("created_at")
        bundle.audit_hash = hashlib.sha256(
            str(sorted(payload.items())).encode()
        ).hexdigest()[:16]
        return bundle

    def deploy_canary(
        self,
        bundle: ModelBundle,
        traffic_percent: float = 10.0,
        serving_mode: str = "lora_fused",
    ) -> Deployment:
        dep = Deployment(
            bundle_id=bundle.bundle_id,
            serving_mode=serving_mode,
            traffic_percent=min(max(traffic_percent, 0.0), 100.0),
            status="canary",
            sLo={"ttft_ms": 200, "tps": 50, "error_rate": 0.01},
        )
        self._deployments[dep.deployment_id] = dep
        return dep

    def promote(self, deployment_id: str) -> Optional[Deployment]:
        dep = self._deployments.get(deployment_id)
        if not dep:
            return None
        dep.status = "stable"
        dep.traffic_percent = 100.0
        return dep

    def rollback(self, deployment_id: str) -> Optional[Deployment]:
        dep = self._deployments.get(deployment_id)
        if not dep:
            return None
        dep.status = "rolled_back"
        dep.traffic_percent = 0.0
        return dep

    def get(self, deployment_id: str) -> Optional[Deployment]:
        return self._deployments.get(deployment_id)


class CanaryMonitor:
    """
    Compara métricas canary vs baseline y decide promover o rollback.
    """

    def __init__(
        self,
        max_error_rate: float = 0.05,
        max_latency_p95_ms: float = 500.0,
        min_success_rate: float = 0.95,
    ) -> None:
        self.max_error_rate = max_error_rate
        self.max_latency_p95_ms = max_latency_p95_ms
        self.min_success_rate = min_success_rate

    def assess(self, canary_metrics: Dict[str, float], baseline_metrics: Dict[str, float]) -> Dict[str, Any]:
        reasons: List[str] = []
        passed = True
        if canary_metrics.get("error_rate", 0.0) > self.max_error_rate:
            passed = False
            reasons.append("error_rate_too_high")
        if canary_metrics.get("latency_p95_ms", 0.0) > self.max_latency_p95_ms:
            passed = False
            reasons.append("latency_p95_too_high")
        if canary_metrics.get("success_rate", 1.0) < self.min_success_rate:
            passed = False
            reasons.append("success_rate_too_low")
        # Regresión respecto a baseline
        if baseline_metrics.get("success_rate", 1.0) - canary_metrics.get("success_rate", 1.0) > 0.02:
            passed = False
            reasons.append("regression_vs_baseline")
        return {"passed": passed, "reasons": reasons, "canary_metrics": canary_metrics, "baseline_metrics": baseline_metrics}


class DriftHallucinationAgent:
    """
    Detecta drift de inputs/concepto y alucinaciones (simulado vía NLI/verificación RAG).
    """

    def __init__(
        self,
        data_drift_threshold: float = 0.25,
        concept_drift_threshold: float = 0.20,
        hallucination_threshold: float = 0.05,
    ) -> None:
        self.data_drift_threshold = data_drift_threshold
        self.concept_drift_threshold = concept_drift_threshold
        self.hallucination_threshold = hallucination_threshold

    def analyze(
        self,
        deployment_id: str,
        recent_inputs: List[str],
        recent_outputs: List[str],
        reference_contexts: List[str],
    ) -> DriftReport:
        # Simulación determinista basada en longitud y palabras clave.
        import random
        random.seed(deployment_id)
        data_drift = random.uniform(0.0, 0.4)
        concept_drift = random.uniform(0.0, 0.35)
        hallucination_rate = random.uniform(0.0, 0.10)
        samples = []
        for inp, out in zip(recent_inputs[:5], recent_outputs[:5]):
            # Heurística simple: si output contiene info no presente en contexto => posible alucinación.
            missing_terms = [w for w in out.lower().split() if w not in " ".join(reference_contexts).lower() and len(w) > 6]
            if missing_terms:
                samples.append({"input": inp, "output": out, "issue": "possible_hallucination"})
        if hallucination_rate > self.hallucination_threshold:
            samples.append({"issue": "hallucination_rate_above_threshold", "rate": hallucination_rate})
        violated = (
            data_drift > self.data_drift_threshold
            or concept_drift > self.concept_drift_threshold
            or hallucination_rate > self.hallucination_threshold
        )
        return DriftReport(
            deployment_id=deployment_id,
            data_drift_score=round(data_drift, 3),
            concept_drift_score=round(concept_drift, 3),
            hallucination_rate=round(hallucination_rate, 3),
            threshold_violated=violated,
            samples=samples,
        )


class FeedbackLoopAgent:
    """
    Convierte feedback de producción en ejemplos de entrenamiento y agenda ciclos
    de re-entrenamiento según impacto.
    """

    def __init__(self, min_feedback_to_trigger: int = 10) -> None:
        self.min_feedback_to_trigger = min_feedback_to_trigger
        self._feedback: List[FeedbackItem] = []
        self._cycles: List[ClosedLoopCycle] = []

    def ingest(self, item: FeedbackItem) -> FeedbackItem:
        self._feedback.append(item)
        return item

    def generate_training_examples(self) -> List[Dict[str, Any]]:
        examples = []
        for fb in self._feedback:
            if fb.label in ("bad", "corrected"):
                output = fb.corrected_output if fb.corrected_output else fb.output_text
                label = "rejected" if fb.label == "bad" else "accepted"
                examples.append({
                    "input": fb.input_text,
                    "output": output,
                    "label": label,
                    "source": fb.source,
                })
        return examples

    def should_trigger_retrain(self, deployment_id: str) -> Optional[ClosedLoopCycle]:
        relevant = [f for f in self._feedback if f.deployment_id == deployment_id]
        negative = [f for f in relevant if f.label in ("bad", "corrected")]
        if len(negative) >= self.min_feedback_to_trigger:
            priority = len(negative) // self.min_feedback_to_trigger
            cycle = ClosedLoopCycle(
                deployment_id=deployment_id,
                triggered_by="feedback_count",
                new_dataset_id=f"feedback-dataset-{deployment_id}",
                priority=priority,
            )
            self._cycles.append(cycle)
            return cycle
        return None

    def trigger_from_drift(self, deployment_id: str, drift_report: DriftReport) -> Optional[ClosedLoopCycle]:
        if not drift_report.threshold_violated:
            return None
        cycle = ClosedLoopCycle(
            deployment_id=deployment_id,
            triggered_by="drift",
            new_dataset_id=f"drift-dataset-{deployment_id}",
            priority=2 if drift_report.hallucination_rate > 0.1 else 1,
        )
        self._cycles.append(cycle)
        return cycle

    def approve_cycle(self, cycle_id: str) -> Optional[ClosedLoopCycle]:
        cycle = next((c for c in self._cycles if c.cycle_id == cycle_id), None)
        if cycle:
            cycle.status = "approved"
        return cycle

    def list_cycles(self, deployment_id: Optional[str] = None) -> List[ClosedLoopCycle]:
        cycles = self._cycles
        if deployment_id:
            cycles = [c for c in cycles if c.deployment_id == deployment_id]
        return cycles
