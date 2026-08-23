"""UC-702 — Pool compartido de capacidad.

Registra nodos (server/nodo/rack, on-premise o en la nube), recibe sus
telemetrías, sumariza la capacidad subutilizada disponible por
sitio/rack/nodo y resuelve asignaciones ("carga a disponibilidad") para
un nodo compartido, aplicación o demanda de servicio.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config import MonitorConfig
from models import (
    Allocation,
    AvailableCapacity,
    NodeInfo,
    NodeRecord,
    ResourceDemand,
    ResourceSnapshot,
)
from underutilization import evaluate


class InsufficientCapacityError(Exception):
    pass


class CapacityPool:
    """Registro en memoria del clúster y su capacidad subutilizada."""

    def __init__(self, config: Optional[MonitorConfig] = None) -> None:
        self.config = config or MonitorConfig()
        self._nodes: Dict[str, NodeRecord] = {}
        self._allocations: Dict[str, Allocation] = {}
        self._lock = threading.RLock()

    # ── Registro e ingestión ────────────────────────────────────────────
    def register_node(self, info: NodeInfo) -> NodeRecord:
        with self._lock:
            record = self._nodes.get(info.node_id)
            if record:
                record.info = info
            else:
                record = NodeRecord(info=info)
                self._nodes[info.node_id] = record
            return record

    def ingest_snapshot(self, node_id: str, snapshot: ResourceSnapshot) -> AvailableCapacity:
        with self._lock:
            record = self._nodes.get(node_id)
            if not record:
                raise KeyError(f"node {node_id} not registered")
            capacity = evaluate(snapshot, self.config.thresholds)
            record.last_snapshot = snapshot
            record.last_capacity = capacity
            record.last_seen = datetime.now(timezone.utc)
            return capacity

    def get_node(self, node_id: str) -> Optional[NodeRecord]:
        return self._nodes.get(node_id)

    def list_nodes(self, include_stale: bool = True) -> List[NodeRecord]:
        now = datetime.now(timezone.utc)
        records = list(self._nodes.values())
        if include_stale:
            return records
        return [r for r in records if not r.is_stale(now, self.config.node_stale_after_seconds)]

    def remove_node(self, node_id: str) -> bool:
        with self._lock:
            return self._nodes.pop(node_id, None) is not None

    # ── Sumarización ─────────────────────────────────────────────────────
    def cluster_summary(self) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        active = [
            r for r in self._nodes.values()
            if not r.is_stale(now, self.config.node_stale_after_seconds) and r.last_capacity
        ]
        total_cpu = sum(r.last_capacity.cpu_cores_available for r in active)
        total_mem = sum(r.last_capacity.memory_available_mb for r in active)
        total_disk = sum(r.last_capacity.disk_available_gb for r in active)
        total_gpu = sum(r.last_capacity.gpu_count_available for r in active)
        total_gpu_mem = sum(r.last_capacity.gpu_memory_available_mb for r in active)

        by_site: Dict[str, Dict[str, float]] = {}
        by_rack: Dict[str, Dict[str, float]] = {}
        for r in active:
            site = r.info.site or "default"
            rack = r.info.rack or "unassigned"
            self._accumulate(by_site, site, r.last_capacity)
            self._accumulate(by_rack, rack, r.last_capacity)

        return {
            "generated_at": now.isoformat(),
            "nodes_total": len(self._nodes),
            "nodes_active": len(active),
            "nodes_subutilized": sum(1 for r in active if r.last_capacity.is_subutilized),
            "capacity_available": {
                "cpu_cores": round(total_cpu, 2),
                "memory_mb": round(total_mem, 2),
                "disk_gb": round(total_disk, 2),
                "gpu_count": total_gpu,
                "gpu_memory_mb": round(total_gpu_mem, 2),
            },
            "by_site": by_site,
            "by_rack": by_rack,
        }

    @staticmethod
    def _accumulate(bucket: Dict[str, Dict[str, float]], key: str, capacity: AvailableCapacity) -> None:
        entry = bucket.setdefault(
            key,
            {"cpu_cores": 0.0, "memory_mb": 0.0, "disk_gb": 0.0, "gpu_count": 0.0, "gpu_memory_mb": 0.0},
        )
        entry["cpu_cores"] = round(entry["cpu_cores"] + capacity.cpu_cores_available, 2)
        entry["memory_mb"] = round(entry["memory_mb"] + capacity.memory_available_mb, 2)
        entry["disk_gb"] = round(entry["disk_gb"] + capacity.disk_available_gb, 2)
        entry["gpu_count"] += capacity.gpu_count_available
        entry["gpu_memory_mb"] = round(entry["gpu_memory_mb"] + capacity.gpu_memory_available_mb, 2)

    # ── Asignación de demanda ───────────────────────────────────────────
    def allocate(self, demand: ResourceDemand) -> Allocation:
        """Selecciona el nodo con mejor ajuste (best-fit) para la demanda,
        entre los nodos activos y con capacidad subutilizada suficiente."""
        with self._lock:
            now = datetime.now(timezone.utc)
            candidates = [
                r for r in self._nodes.values()
                if not r.is_stale(now, self.config.node_stale_after_seconds)
                and r.last_capacity
                and r.last_capacity.is_subutilized
                and r.last_capacity.cpu_cores_available >= demand.cpu_cores
                and r.last_capacity.memory_available_mb >= demand.memory_mb
                and r.last_capacity.disk_available_gb >= demand.disk_gb
                and r.last_capacity.gpu_count_available >= demand.gpu_count
                and r.last_capacity.gpu_memory_available_mb >= demand.gpu_memory_mb
            ]
            if demand.preferred_site:
                preferred = [c for c in candidates if c.info.site == demand.preferred_site]
                candidates = preferred or candidates

            if not candidates:
                raise InsufficientCapacityError(
                    "No hay nodos con capacidad subutilizada suficiente para la demanda solicitada"
                )

            # Best-fit: minimizar el remanente de CPU tras asignar (evita fragmentar nodos grandes).
            best = min(candidates, key=lambda r: r.last_capacity.cpu_cores_available - demand.cpu_cores)

            allocation = Allocation(
                allocation_id=str(uuid.uuid4()),
                requester=demand.requester,
                node_id=best.info.node_id,
                cpu_cores=demand.cpu_cores,
                memory_mb=demand.memory_mb,
                disk_gb=demand.disk_gb,
                gpu_count=demand.gpu_count,
                gpu_memory_mb=demand.gpu_memory_mb,
                created_at=now,
            )
            # Descuenta optimistamente del remanente conocido hasta la próxima telemetría.
            best.last_capacity.cpu_cores_available -= demand.cpu_cores
            best.last_capacity.memory_available_mb -= demand.memory_mb
            best.last_capacity.disk_available_gb -= demand.disk_gb
            best.last_capacity.gpu_count_available -= demand.gpu_count
            best.last_capacity.gpu_memory_available_mb -= demand.gpu_memory_mb

            self._allocations[allocation.allocation_id] = allocation
            return allocation

    def release(self, allocation_id: str) -> Allocation:
        with self._lock:
            allocation = self._allocations.get(allocation_id)
            if not allocation:
                raise KeyError(f"allocation {allocation_id} not found")
            if allocation.released:
                return allocation
            allocation.released = True
            node = self._nodes.get(allocation.node_id)
            if node and node.last_capacity:
                node.last_capacity.cpu_cores_available += allocation.cpu_cores
                node.last_capacity.memory_available_mb += allocation.memory_mb
                node.last_capacity.disk_available_gb += allocation.disk_gb
                node.last_capacity.gpu_count_available += allocation.gpu_count
                node.last_capacity.gpu_memory_available_mb += allocation.gpu_memory_mb
            return allocation

    def list_allocations(self, requester: Optional[str] = None) -> List[Allocation]:
        allocations = list(self._allocations.values())
        if requester:
            allocations = [a for a in allocations if a.requester == requester]
        return allocations
