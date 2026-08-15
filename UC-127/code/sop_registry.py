"""
Codificando.AI - UC-127
Registro de metadatos de los SOP (Standard Operating Procedures) definidos
en `playbooks/*.yaml`. Alimenta el panel "Salud del SOP (Wiki.js)" del
dashboard de resiliencia: para cada SOP se registra la última vez que fue
actualizado y el último incidente que lo disparó, permitiendo marcar en
ámbar los manuales que no se han revisado en `sop_stale_days` (ver
`config.DetectionThresholds.sop_stale_days`).

En un despliegue real, esta información vive en Wiki.js (versionada en
Git); esta clase mantiene una réplica en memoria/local sincronizada por
`WikiClient` para poder exponerla vía API sin depender de Wiki.js en
pruebas o entornos de desarrollo.
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


@dataclass
class SopMetadata:
    playbook_name: str
    wiki_page_id: int
    last_updated_at: Optional[str] = None
    last_incident_id: Optional[str] = None
    update_count: int = 0

    def to_dict(self) -> Dict[str, object]:
        return {
            "playbook_name": self.playbook_name,
            "wiki_page_id": self.wiki_page_id,
            "last_updated_at": self.last_updated_at,
            "last_incident_id": self.last_incident_id,
            "update_count": self.update_count,
        }

    def days_since_update(self) -> Optional[float]:
        if not self.last_updated_at:
            return None
        last = datetime.fromisoformat(self.last_updated_at)
        now = datetime.now(timezone.utc)
        return (now - last).total_seconds() / 86400.0


# Mapeo de playbook -> ID de página en Wiki.js (equivalente al mapeo
# `_get_sop_page_id` de la versión original de UC-127).
WIKI_PAGE_ID_MAP: Dict[str, int] = {
    "unsafe_generation": 101,
    "system_overload": 102,
    "hallucination": 103,
    "prompt_injection": 104,
    "data_leak": 105,
    "quality_degradation": 106,
    "tool_failure": 107,
    "latency_anomaly": 108,
    "cost_anomaly": 109,
}


class SopRegistry:
    """Registro thread-safe de metadatos de SOP, en memoria."""

    def __init__(self):
        self._lock = threading.Lock()
        self._sops: Dict[str, SopMetadata] = {
            name: SopMetadata(playbook_name=name, wiki_page_id=page_id)
            for name, page_id in WIKI_PAGE_ID_MAP.items()
        }

    def get_page_id(self, playbook_name: str) -> int:
        return WIKI_PAGE_ID_MAP.get(playbook_name, 999)

    def record_update(self, playbook_name: str, incident_id: str) -> SopMetadata:
        with self._lock:
            meta = self._sops.setdefault(
                playbook_name,
                SopMetadata(playbook_name=playbook_name, wiki_page_id=self.get_page_id(playbook_name)),
            )
            meta.last_updated_at = datetime.now(timezone.utc).isoformat()
            meta.last_incident_id = incident_id
            meta.update_count += 1
            return meta

    def list_sops(self) -> List[SopMetadata]:
        with self._lock:
            return list(self._sops.values())

    def get(self, playbook_name: str) -> Optional[SopMetadata]:
        with self._lock:
            return self._sops.get(playbook_name)


SOP_REGISTRY = SopRegistry()
