"""UC-700 — Capa de observabilidad: recolección de telemetría.

Simula y normaliza métricas de:
  - DCGM (GPU NVIDIA)
  - Kubernetes (nodo / pod)
  - Runtime de entrenamiento
  - Red / almacenamiento / energía

En producción estos adaptadores leerían de:
  - /metrics de DCGM Exporter
  - kubelet / kube-state-metrics
  - Prometheus query API
  - Slurm / Azure CycleCloud
"""

from __future__ import annotations

import random
from datetime import datetime
from typing import Dict, List, Optional

from config import HealthState
from models import Device, Node, TelemetrySnapshot, TrainingJob


class DCGMCollector:
    """Recolector de métricas de GPU NVIDIA."""

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)

    def sample(self, device: Device, inject_failure: bool = False) -> Dict[str, float]:
        base = {
            "DCGM_FI_DEV_GPU_UTIL": min(100.0, max(0.0, device.util_pct + self.rng.gauss(0, 3))),
            "DCGM_FI_DEV_FB_USED": device.vram_used_gb,
            "DCGM_FI_DEV_FB_TOTAL": device.vram_total_gb,
            "DCGM_FI_DEV_GPU_TEMP": device.temperature_c + self.rng.gauss(0, 1.5),
            "DCGM_FI_DEV_POWER_USAGE": 250.0 + self.rng.gauss(0, 10),
            "DCGM_FI_DEV_XID_ERRORS": float(device.memory_errors),
            "DCGM_FI_DEV_PCIE_REPLAY": self.rng.random() * 100,
            "DCGM_FI_DEV_MEM_COPY_UTIL": min(100.0, max(0.0, device.util_pct * 0.8 + self.rng.gauss(0, 5))),
        }
        if inject_failure:
            base["DCGM_FI_DEV_GPU_TEMP"] = 98.0
            base["DCGM_FI_DEV_FB_USED"] = device.vram_total_gb * 0.99
            base["DCGM_FI_DEV_XID_ERRORS"] += 8.0
            base["DCGM_FI_DEV_PCIE_REPLAY"] += 50.0
        return base


class KubernetesCollector:
    """Recolector de métricas del plano de Kubernetes."""

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)

    def sample(self, node: Node) -> Dict[str, float]:
        return {
            "kube_node_status_condition": 1.0 if node.state == HealthState.HEALTHY else 0.0,
            "container_cpu_usage_seconds_total": 4.0 + self.rng.random() * 2.0,
            "container_memory_working_set_bytes": 64e9 + self.rng.random() * 16e9,
            "kube_pod_status_ready": 1.0,
            "node_network_receive_bytes_total": 1e9 + self.rng.random() * 1e9,
            "node_network_transmit_drop_total": self.rng.random() * 0.3,
        }


class TrainingCollector:
    """Recolector de métricas del runtime de entrenamiento."""

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)

    def sample(self, job: TrainingJob, degraded: bool = False) -> Dict[str, float]:
        base_samples = job.samples_per_sec_baseline
        if degraded:
            base_samples *= 0.7
        return {
            "training_loss": job.loss_baseline + self.rng.gauss(0, 0.02),
            "training_samples_per_sec": base_samples + self.rng.gauss(0, 500),
            "training_step_time_ms": 120.0 + self.rng.gauss(0, 10),
            "training_grad_norm": 1.0 + self.rng.random(),
            "training_checkpoint_age_sec": self.rng.random() * 300,
        }


class TelemetryCollector:
    """Orquesta la recolección de telemetría para nodos y jobs."""

    def __init__(self):
        self.dcgm = DCGMCollector()
        self.k8s = KubernetesCollector()
        self.training = TrainingCollector()

    def collect_node(
        self,
        node: Node,
        device: Optional[Device] = None,
        inject_failure: bool = False,
    ) -> TelemetrySnapshot:
        metrics: Dict[str, float] = {}
        metrics.update(self.k8s.sample(node))
        target_device = device or (node.devices[0] if node.devices else None)
        if target_device:
            metrics.update(self.dcgm.sample(target_device, inject_failure=inject_failure))
        return TelemetrySnapshot(
            node_id=node.id,
            device_id=target_device.id if target_device else None,
            timestamp=datetime.utcnow(),
            metrics=metrics,
            events=[],
            source="dcgm+k8s",
        )

    def collect_job(self, job: TrainingJob, degraded: bool = False) -> TelemetrySnapshot:
        metrics = self.training.sample(job, degraded=degraded)
        return TelemetrySnapshot(
            node_id=",".join(job.nodes),
            timestamp=datetime.utcnow(),
            metrics=metrics,
            events=[],
            source="training-runtime",
        )

    def inject_memory_failure_signature(self, snapshot: TelemetrySnapshot) -> TelemetrySnapshot:
        """Aumenta señales para simular riesgo elevado de fallo de memoria."""
        snapshot.metrics["DCGM_FI_DEV_FB_USED"] = 78.0
        snapshot.metrics["DCGM_FI_DEV_FB_TOTAL"] = 80.0
        snapshot.metrics["DCGM_FI_DEV_XID_ERRORS"] = 12.0
        snapshot.metrics["DCGM_FI_DEV_PCIE_REPLAY"] = 85.0
        snapshot.metrics["DCGM_FI_DEV_GPU_TEMP"] = 92.0
        snapshot.events.append("dcgm_xid_memory_error")
        snapshot.events.append("pcie_replay_threshold_exceeded")
        return snapshot
