"""
UC-075 — Registro de versiones, freeze de datos y rollback seguro.

- VersionFreezeRegistry: congela y versiona datasets con hash de contenido
  (también anti-tampering, alineado con UC-087 provenance).
- ChampionRegistry: estado campeón/candidato/canchallenger por agente,
  con historial y rollback al último campeón estable.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from models_075 import FrozenDataset


# ---------------------------------------------------------------------------
# Freeze + versionado de datasets
# ---------------------------------------------------------------------------

class VersionFreezeRegistry:
    """Congela batches con hash de contenido y versión monótona."""

    def __init__(self, hash_algorithm: str = "sha256") -> None:
        self.hash_algorithm = hash_algorithm
        self._frozen: Dict[str, FrozenDataset] = {}
        self._counter = 0

    def freeze(
        self,
        records: List[Dict[str, Any]],
        replay: Optional[List[Dict[str, Any]]] = None,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> FrozenDataset:
        replay = list(replay or [])
        payload = json.dumps(records, sort_keys=True, default=str)
        digest = hashlib.new(self.hash_algorithm, payload.encode()).hexdigest()
        self._counter += 1
        version = f"ds-{int(time.time())}-{self._counter:04d}"
        snap = FrozenDataset(
            dataset_version=version,
            dataset_hash=digest,
            n_records=len(records) + len(replay),
            n_replay=len(replay),
            provenance=provenance or {},
            records=list(records) + replay,
        )
        self._frozen[version] = snap
        return snap

    def get(self, version: str) -> Optional[FrozenDataset]:
        return self._frozen.get(version)

    def verify(self, version: str) -> bool:
        """Re-verifica el hash: False = tampering detectado."""
        snap = self._frozen.get(version)
        if snap is None:
            return False
        payload = json.dumps(
            snap.records[: snap.n_records - snap.n_replay],
            sort_keys=True,
            default=str,
        )
        return hashlib.new(self.hash_algorithm, payload.encode()).hexdigest() == snap.dataset_hash

    def list_versions(self) -> List[str]:
        return sorted(self._frozen.keys())


# ---------------------------------------------------------------------------
# Registro campeón/candidato + rollback
# ---------------------------------------------------------------------------

@dataclass
class VersionState:
    """Estado de una versión de modelo para un agente."""
    version_id: str
    role: str = "candidate"     # candidate | champion | canary | rolled_back
    metrics: Dict[str, float] = field(default_factory=dict)
    promoted_at: Optional[float] = None
    rolled_back_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version_id": self.version_id,
            "role": self.role,
            "metrics": self.metrics,
            "promoted_at": self.promoted_at,
            "rolled_back_at": self.rolled_back_at,
        }


class ChampionRegistry:
    """Gestiona campeón, candidato en canary y rollback por agente."""

    STABLE_ROLES = ("champion", "rolled_back")

    def __init__(self, initial_version: str = "v-baseline") -> None:
        self._champions: Dict[str, VersionState] = {}
        self._history: Dict[str, List[VersionState]] = {}
        self._default = initial_version

    def bootstrap(self, agent_id: str, metrics: Optional[Dict[str, float]] = None) -> VersionState:
        champ = VersionState(
            version_id=self._default,
            role="champion",
            metrics=metrics or {"accuracy": 0.8},
            promoted_at=time.time(),
        )
        self._champions.setdefault(agent_id, champ)
        self._history.setdefault(agent_id, [champ])
        return self._champions[agent_id]

    def current_champion(self, agent_id: str) -> VersionState:
        if agent_id not in self._champions:
            return self.bootstrap(agent_id)
        return self._champions[agent_id]

    def register_canary(self, agent_id: str, version_id: str, metrics: Dict[str, float]) -> VersionState:
        state = VersionState(version_id=version_id, role="canary", metrics=dict(metrics))
        self._history.setdefault(agent_id, []).append(state)
        return state

    def promote(self, agent_id: str, version_id: str) -> VersionState:
        champ = self.current_champion(agent_id)
        new = VersionState(
            version_id=version_id,
            role="champion",
            metrics=dict(
                self._find_history(agent_id, version_id).metrics
                if self._find_history(agent_id, version_id) else {}
            ),
            promoted_at=time.time(),
        )
        self._champions[agent_id] = new
        self._history.setdefault(agent_id, []).append(new)
        return new

    def rollback(self, agent_id: str) -> VersionState:
        """Vuelve al último campeón de la historia anterior al actual."""
        history = self._history.get(agent_id, [])
        stable = [v for v in history if v.role in self.STABLE_ROLES]
        if len(stable) < 2:
            return self.current_champion(agent_id)
        previous = stable[-2]
        restored = VersionState(
            version_id=previous.version_id,
            role="champion",
            metrics=dict(previous.metrics),
            promoted_at=time.time(),
        )
        self._champions[agent_id] = restored
        self._history.setdefault(agent_id, []).append(restored)
        return restored

    def _find_history(self, agent_id: str, version_id: str) -> Optional[VersionState]:
        for v in reversed(self._history.get(agent_id, [])):
            if v.version_id == version_id:
                return v
        return None

    def history(self, agent_id: str) -> List[Dict[str, Any]]:
        return [v.to_dict() for v in self._history.get(agent_id, [])]

    def status(self) -> Dict[str, Any]:
        return {
            agent_id: {
                "champion": champ.to_dict(),
                "history": [v.version_id for v in self._history.get(agent_id, [])],
            }
            for agent_id, champ in self._champions.items()
        }
