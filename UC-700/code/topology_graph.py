"""UC-700 — Grafo de inventario y topología.

Campus → Zona → Sala → Rack → Nodo → Dispositivo → Workload → Modelo
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from models import Device, Node, TrainingJob


class TopologyGraph:
    """Grafo de dependencias para análisis de impacto."""

    def __init__(self):
        self.nodes: Dict[str, Node] = {}
        self.devices: Dict[str, Device] = {}
        self.jobs: Dict[str, TrainingJob] = {}
        self.device_to_node: Dict[str, str] = {}
        self.node_to_jobs: Dict[str, List[str]] = {}

    def add_node(self, node: Node) -> None:
        self.nodes[node.id] = node
        for device in node.devices:
            self.devices[device.id] = device
            self.device_to_node[device.id] = node.id

    def add_job(self, job: TrainingJob) -> None:
        self.jobs[job.id] = job
        for node_id in job.nodes:
            self.node_to_jobs.setdefault(node_id, []).append(job.id)

    def get_device_node(self, device_id: str) -> Optional[Node]:
        node_id = self.device_to_node.get(device_id)
        return self.nodes.get(node_id) if node_id else None

    def get_scope(self, node_id: str, device_ids: Optional[List[str]] = None) -> Tuple[str, List[str], List[str]]:
        """Determina el alcance del fallo: device, node, rack, zone, domain, region."""
        node = self.nodes.get(node_id)
        if not node:
            return "unknown", [node_id], device_ids or []

        affected_nodes = [node_id]
        affected_devices = list(device_ids or [])

        # Si hay múltiples dispositivos afectados en el mismo nodo -> node scope
        # Si varios nodos del mismo rack están en FAILED -> rack scope
        # Heurística simple: un único dispositivo => device scope
        if not affected_devices:
            scope = "node"
        elif len(affected_devices) == 1:
            scope = "device"
        else:
            scope = "node"

        # Simulación: si el rack tiene más de un nodo en FAILED, sube a rack
        rack_failed = [n for n in self.nodes.values() if n.rack == node.rack and n.state == "FAILED"]
        if len(rack_failed) > 1:
            scope = "rack"
            affected_nodes = [n.id for n in self.nodes.values() if n.rack == node.rack]

        return scope, affected_nodes, affected_devices

    def affected_workloads(self, node_ids: List[str], device_ids: List[str]) -> Dict[str, List[str]]:
        job_ids: Dict[str, List[str]] = {}
        for node_id in node_ids:
            for job_id in self.node_to_jobs.get(node_id, []):
                job_ids.setdefault(job_id, []).append(node_id)
        return job_ids

    def get_homologous_nodes(self, node_id: str) -> List[Node]:
        """Retorna nodos homólogos (misma zona, distinto rack) para comparación."""
        node = self.nodes.get(node_id)
        if not node:
            return []
        return [n for n in self.nodes.values() if n.zone == node.zone and n.id != node_id]

    def to_dict(self) -> Dict[str, any]:
        return {
            "nodes": [n.id for n in self.nodes.values()],
            "devices": [d.id for d in self.devices.values()],
            "jobs": [j.id for j in self.jobs.values()],
            "node_to_jobs": self.node_to_jobs,
        }
