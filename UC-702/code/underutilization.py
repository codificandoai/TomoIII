"""UC-702 — Análisis de subutilización de recursos.

Convierte una foto instantánea (`ResourceSnapshot`) en la capacidad
disponible ("subutilizada") que puede sumarizarse y ofrecerse al pool
compartido, aplicando los umbrales configurados.
"""

from __future__ import annotations

from typing import List

from config import UnderutilizationThresholds
from models import AvailableCapacity, ResourceSnapshot


def evaluate(snapshot: ResourceSnapshot, thresholds: UnderutilizationThresholds) -> AvailableCapacity:
    reasons: List[str] = []

    cpu_idle_pct = snapshot.cpu_idle_pct
    cpu_cores_available = 0.0
    if cpu_idle_pct >= thresholds.cpu_idle_pct_min:
        cpu_cores_available = snapshot.cpu_count_logical * (cpu_idle_pct / 100.0)
        reasons.append(f"cpu_idle_{cpu_idle_pct:.1f}pct")

    memory_available_mb = 0.0
    if snapshot.memory_available_pct >= thresholds.memory_available_pct_min:
        memory_available_mb = snapshot.memory_available_mb
        reasons.append(f"memory_available_{snapshot.memory_available_pct:.1f}pct")

    disk_available_gb = 0.0
    if snapshot.disk_available_pct >= thresholds.disk_available_pct_min:
        disk_available_gb = snapshot.disk_free_gb
        reasons.append(f"disk_available_{snapshot.disk_available_pct:.1f}pct")

    gpu_count_available = 0
    gpu_memory_available_mb = 0.0
    for gpu in snapshot.gpus:
        idle_pct = gpu.idle_pct
        mem_free_pct = gpu.memory_free_pct
        # Si no se puede medir utilización (p.ej. Apple Silicon sin NVML),
        # se considera potencialmente disponible pero se documenta la razón.
        if idle_pct is None and mem_free_pct is None:
            gpu_count_available += 1
            reasons.append(f"gpu{gpu.index}_utilization_unknown")
            continue
        idle_ok = idle_pct is None or idle_pct >= thresholds.gpu_idle_pct_min
        mem_ok = mem_free_pct is None or mem_free_pct >= thresholds.gpu_memory_free_pct_min
        if idle_ok and mem_ok:
            gpu_count_available += 1
            if gpu.memory_free_mb:
                gpu_memory_available_mb += gpu.memory_free_mb
            reasons.append(f"gpu{gpu.index}_idle_{(idle_pct or 0):.1f}pct")

    is_subutilized = any(
        [
            cpu_cores_available > 0,
            memory_available_mb > 0,
            disk_available_gb > 0,
            gpu_count_available > 0,
        ]
    )

    return AvailableCapacity(
        cpu_cores_available=cpu_cores_available,
        memory_available_mb=memory_available_mb,
        disk_available_gb=disk_available_gb,
        gpu_count_available=gpu_count_available,
        gpu_memory_available_mb=gpu_memory_available_mb,
        is_subutilized=is_subutilized,
        reasons=reasons,
    )
