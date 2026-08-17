"""UC-700 — Agente de aislamiento.

Paso 4: Aislar el componente.
Niveles: acelerador, partición, nodo, rack, zona, volumen, dominio energético, región.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from config import HealthState
from models import Device, ImpactReport, Node, RemediationPlan, TrainingJob


class IsolationAgent:
    """Paso 4: Aislar el componente afectado sin perder el estado lógico del entrenamiento."""

    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self._operations: List[Dict[str, str]] = []

    def isolate(
        self,
        node: Node,
        impact: ImpactReport,
        plan: Optional[RemediationPlan] = None,
    ) -> Dict[str, any]:
        scope = impact.scope
        result: Dict[str, any] = {
            "scope": scope,
            "node_id": node.id,
            "operations": [],
            "devices_quarantined": [],
            "nodes_cordoned": [],
            "nodes_drained": [],
        }

        if scope in ("device",):
            for device_id in impact.affected_devices:
                device = next((d for d in node.devices if d.id == device_id), None)
                if device:
                    self._quarantine_device(device)
                    result["devices_quarantined"].append(device_id)
                    result["operations"].append({"action": "quarantine_device", "target": device_id})

        if scope in ("device", "node"):
            self._cordon_node(node)
            result["nodes_cordoned"].append(node.id)
            result["operations"].append({"action": "cordon_node", "target": node.id})

        if scope in ("node", "rack"):
            self._drain_node(node, impact.affected_jobs)
            result["nodes_drained"].append(node.id)
            result["operations"].append({"action": "drain_node", "target": node.id})

        if scope == "rack":
            node.taints.append("rack-degraded=true:NoSchedule")
            result["operations"].append({"action": "taint_rack", "target": node.rack})

        if scope in ("zone", "domain"):
            node.taints.append("zone-failure=true:NoSchedule")
            result["operations"].append({"action": "stop_new_allocations", "target": node.zone})

        return result

    def _quarantine_device(self, device: Device) -> None:
        device.state = HealthState.QUARANTINED
        if not self.dry_run:
            # En producción: kubectl label node $node nvidia.com/gpu.health=unhealthy
            # kubectl patch node $node ... device plugin unhealthy flag
            pass
        self._operations.append({"action": "quarantine_device", "target": device.id})

    def _cordon_node(self, node: Node) -> None:
        node.state = HealthState.QUARANTINED
        if not self.dry_run:
            # kubectl cordon $node
            pass
        self._operations.append({"action": "cordon", "target": node.id})

    def _drain_node(self, node: Node, job_ids: List[str]) -> None:
        node.state = HealthState.RECOVERING
        if not self.dry_run:
            # kubectl drain $node --ignore-daemonsets --delete-emptydir-data
            # En entrenamiento distribuido: checkpoint graceful + detach workers
            pass
        self._operations.append({"action": "drain", "target": node.id, "jobs": job_ids})

    def get_operations(self) -> List[Dict[str, str]]:
        return self._operations
