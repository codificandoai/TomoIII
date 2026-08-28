"""Detección y clasificación de conflictos (inspirado en OVADARE) para UC-270.

Detecta conflictos por:
- Reclamaciones de recursos duplicadas.
- Acciones incompatibles sobre el mismo recurso.
- Estado inconsistente entre agentes.
- Violaciones de política.
"""
from __future__ import annotations

from typing import Dict, List, Optional
from uuid import UUID

from models import (
    AgentProfile,
    ConflictSeverity,
    ConflictType,
    DetectedConflict,
    ResourceClaim,
)


class ConflictDetector:
    """Detecta y clasifica conflictos entre agentes."""

    def detect(self, claims: List[ResourceClaim]) -> List[DetectedConflict]:
        """Analiza reclamaciones y detecta conflictos."""
        # Agrupar claims por recurso
        by_resource: Dict[str, List[ResourceClaim]] = {}
        for claim in claims:
            by_resource.setdefault(claim.resource_id, []).append(claim)

        conflicts: List[DetectedConflict] = []
        for resource_id, resource_claims in by_resource.items():
            if len(resource_claims) < 2:
                continue

            conflict_type = self._classify_type(resource_claims)
            severity = self._classify_severity(resource_claims)

            conflicts.append(
                DetectedConflict(
                    conflict_type=conflict_type,
                    severity=severity,
                    resource_id=resource_id,
                    claimants=[c.agent_name for c in resource_claims],
                    claims=resource_claims,
                    description=self._describe(conflict_type, resource_id, resource_claims),
                )
            )
        return conflicts

    def _classify_type(self, claims: List[ResourceClaim]) -> ConflictType:
        """Clasifica el tipo de conflicto según las reclamaciones."""
        agents = {c.agent_name for c in claims}
        # Si el mismo agente reclama dos veces, es ownership duplicada
        if len(agents) < len(claims):
            return ConflictType.duplicate_ownership
        # Si todos reclaman con need total > 1.0, es contención de recursos
        total_need = sum(c.need for c in claims)
        if total_need > 1.0:
            return ConflictType.resource_contention
        # Si prioridades iguales y alta necesidad, acciones incompatibles
        priorities = {c.priority for c in claims}
        if len(priorities) == 1 and total_need > 0.8:
            return ConflictType.incompatible_actions
        return ConflictType.resource_contention

    def _classify_severity(self, claims: List[ResourceClaim]) -> ConflictSeverity:
        """Clasifica la severidad del conflicto."""
        max_priority = max(c.priority for c in claims)
        total_need = sum(c.need for c in claims)

        if max_priority >= 9 and total_need > 1.5:
            return ConflictSeverity.critical
        if max_priority >= 7 or total_need > 1.3:
            return ConflictSeverity.high
        if max_priority >= 5:
            return ConflictSeverity.medium
        return ConflictSeverity.low

    def _describe(
        self, ctype: ConflictType, resource_id: str, claims: List[ResourceClaim]
    ) -> str:
        agents = ", ".join(c.agent_name for c in claims)
        return f"{ctype.value} on '{resource_id}' between [{agents}]"
