"""
Codificando.AI - UC-127
Cargador de manuales de procedimiento codificados (playbooks). Los
playbooks se definen como archivos YAML versionados en Git
(`playbooks/*.yaml`), no como documentos estáticos, de forma que un
cambio en el manual de procedimientos es un *pull request* auditable y
desplegable — tal como describe la sección "Manuales de Procedimientos
Codificados" de `UC-127.md`.
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import yaml

from incident_types import IncidentType

logger = logging.getLogger(__name__)

PLAYBOOKS_DIR = os.path.dirname(os.path.abspath(__file__))


@dataclass
class PlaybookStep:
    name: str
    integration: str
    method: str
    requires_approval: bool = False
    reversible: bool = True
    params: Dict[str, object] = field(default_factory=dict)


@dataclass
class Playbook:
    name: str
    incident_type: IncidentType
    description: str
    trigger_description: str
    steps: List[PlaybookStep] = field(default_factory=list)


class PlaybookLoader:
    """Carga y cachea los playbooks codificados desde `playbooks/*.yaml`."""

    def __init__(self, directory: str = PLAYBOOKS_DIR):
        self.directory = directory
        self._by_incident_type: Dict[IncidentType, Playbook] = {}
        self._by_name: Dict[str, Playbook] = {}
        self.reload()

    def reload(self) -> None:
        """(Re)carga todos los playbooks desde disco. Se invoca al iniciar
        el orquestador y puede invocarse tras un `git pull` para aplicar
        actualizaciones de SOP sin reiniciar el servicio."""
        self._by_incident_type.clear()
        self._by_name.clear()

        if not os.path.isdir(self.directory):
            logger.warning(f"Directorio de playbooks no encontrado: {self.directory}")
            return

        for filename in sorted(os.listdir(self.directory)):
            if not filename.endswith((".yaml", ".yml")):
                continue
            path = os.path.join(self.directory, filename)
            try:
                playbook = self._load_file(path)
            except Exception as e:
                logger.error(f"Error cargando playbook {filename}: {e}")
                continue
            self._by_name[playbook.name] = playbook
            self._by_incident_type[playbook.incident_type] = playbook

        logger.info(f"Playbooks cargados: {list(self._by_name.keys())}")

    def _load_file(self, path: str) -> Playbook:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        steps = [
            PlaybookStep(
                name=s["name"],
                integration=s["integration"],
                method=s["method"],
                requires_approval=bool(s.get("requires_approval", False)),
                reversible=bool(s.get("reversible", True)),
                params=s.get("params", {}) or {},
            )
            for s in raw.get("steps", [])
        ]

        return Playbook(
            name=raw["name"],
            incident_type=IncidentType(raw["incident_type"]),
            description=raw.get("description", "").strip(),
            trigger_description=raw.get("trigger_description", ""),
            steps=steps,
        )

    def get_by_incident_type(self, incident_type: IncidentType) -> Optional[Playbook]:
        return self._by_incident_type.get(incident_type)

    def get_by_name(self, name: str) -> Optional[Playbook]:
        return self._by_name.get(name)

    def list_playbooks(self) -> List[Playbook]:
        return list(self._by_name.values())
