"""UC-702 — Métricas Prometheus.

Expone:
  - uc702_cpu_usage_percent / uc702_cpu_idle_cores_available
  - uc702_memory_available_mb
  - uc702_disk_available_gb
  - uc702_gpu_utilization_percent / uc702_gpu_memory_free_mb
  - uc702_net_sent_bps / uc702_net_recv_bps
  - uc702_node_subutilized
  - uc702_pool_capacity_available
  - uc702_spot_interruptions_total
"""

from __future__ import annotations

from typing import Optional

try:
    from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest
except ImportError:  # pragma: no cover - permite importar sin prometheus_client instalado
    CONTENT_TYPE_LATEST = "text/plain; charset=utf-8"

    def generate_latest(*_args, **_kwargs):
        return b""

    class _Metric:
        def __init__(self, *args, **kwargs):
            pass

        def labels(self, *args, **kwargs):
            return self

        def set(self, *args, **kwargs):
            pass

        def inc(self, *args, **kwargs):
            pass

    class Gauge(_Metric):
        pass

    class Counter(_Metric):
        pass


class UC702Metrics:
    def __init__(self, namespace: str = "uc702") -> None:
        self.namespace = namespace
        self.cpu_usage_percent = Gauge(
            f"{namespace}_cpu_usage_percent", "Uso de CPU por nodo", ["node_id"]
        )
        self.cpu_cores_available = Gauge(
            f"{namespace}_cpu_cores_available", "Núcleos de CPU subutilizados disponibles", ["node_id"]
        )
        self.memory_available_mb = Gauge(
            f"{namespace}_memory_available_mb", "Memoria disponible/subutilizada (MB)", ["node_id"]
        )
        self.disk_available_gb = Gauge(
            f"{namespace}_disk_available_gb", "Disco disponible/subutilizado (GB)", ["node_id"]
        )
        self.gpu_utilization_percent = Gauge(
            f"{namespace}_gpu_utilization_percent", "Utilización de GPU", ["node_id", "gpu_index"]
        )
        self.gpu_memory_free_mb = Gauge(
            f"{namespace}_gpu_memory_free_mb", "Memoria libre de GPU (MB)", ["node_id", "gpu_index"]
        )
        self.net_sent_bps = Gauge(f"{namespace}_net_sent_bps", "Tasa de envío de red (bps)", ["node_id"])
        self.net_recv_bps = Gauge(f"{namespace}_net_recv_bps", "Tasa de recepción de red (bps)", ["node_id"])
        self.node_subutilized = Gauge(
            f"{namespace}_node_subutilized", "1 si el nodo tiene capacidad subutilizada", ["node_id"]
        )
        self.pool_cpu_cores_available = Gauge(
            f"{namespace}_pool_cpu_cores_available", "Total de núcleos disponibles en el pool"
        )
        self.pool_memory_available_mb = Gauge(
            f"{namespace}_pool_memory_available_mb", "Total de memoria disponible en el pool (MB)"
        )
        self.pool_disk_available_gb = Gauge(
            f"{namespace}_pool_disk_available_gb", "Total de disco disponible en el pool (GB)"
        )
        self.pool_gpu_count_available = Gauge(
            f"{namespace}_pool_gpu_count_available", "Total de GPUs disponibles en el pool"
        )
        self.spot_interruptions_total = Counter(
            f"{namespace}_spot_interruptions_total", "Total de interrupciones spot detectadas", ["node_id", "provider"]
        )

    def record_node_snapshot(self, node_id: str, snapshot_dict: dict, capacity_dict: dict) -> None:
        self.cpu_usage_percent.labels(node_id=node_id).set(snapshot_dict.get("cpu_percent", 0.0))
        self.cpu_cores_available.labels(node_id=node_id).set(capacity_dict.get("cpu_cores_available", 0.0))
        self.memory_available_mb.labels(node_id=node_id).set(capacity_dict.get("memory_available_mb", 0.0))
        self.disk_available_gb.labels(node_id=node_id).set(capacity_dict.get("disk_available_gb", 0.0))
        self.net_sent_bps.labels(node_id=node_id).set(snapshot_dict.get("net_sent_rate_bps", 0.0))
        self.net_recv_bps.labels(node_id=node_id).set(snapshot_dict.get("net_recv_rate_bps", 0.0))
        self.node_subutilized.labels(node_id=node_id).set(1 if capacity_dict.get("is_subutilized") else 0)
        for gpu in snapshot_dict.get("gpus", []):
            idx = str(gpu.get("index"))
            if gpu.get("utilization_pct") is not None:
                self.gpu_utilization_percent.labels(node_id=node_id, gpu_index=idx).set(gpu["utilization_pct"])
            if gpu.get("memory_free_mb") is not None:
                self.gpu_memory_free_mb.labels(node_id=node_id, gpu_index=idx).set(gpu["memory_free_mb"])

    def record_pool_summary(self, summary: dict) -> None:
        capacity = summary.get("capacity_available", {})
        self.pool_cpu_cores_available.set(capacity.get("cpu_cores", 0.0))
        self.pool_memory_available_mb.set(capacity.get("memory_mb", 0.0))
        self.pool_disk_available_gb.set(capacity.get("disk_gb", 0.0))
        self.pool_gpu_count_available.set(capacity.get("gpu_count", 0))

    def record_spot_interruption(self, node_id: str, provider: str) -> None:
        self.spot_interruptions_total.labels(node_id=node_id, provider=provider).inc()

    def render(self) -> bytes:
        return generate_latest()
