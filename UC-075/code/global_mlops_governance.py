"""
UC-075 — MLOps global y multi-región: metadatos, artefactos, jurisdicción,
recuperación ante desastres y resolución de conflictos.

Esta capa extiende el registro local de UC-075 para operaciones a gran escala
en múltiples regiones. Proporciona:

- Registro global de artefactos (modelos, datasets, checkpoints) con linaje,
  checksums y firmas.
- Almacenes regionales federados con sincronización y detección de conflictos.
- Políticas de jurisdicción (data residency, retención, cifrado, legal hold).
- Resolución automática de conflictos con quorum y fallback a revisión humana.
- Caché regional de metadatos/artefactos para baja latencia.
- Gestión del ciclo de vida: tiering (hot/warm/cold), retención y garbage
  collection con legal-hold awareness.
- Plan de recuperación ante desastres con RPO/RTO, backups y failover.

Todo se mantiene como capa externa sin modificar los motores internos de
otras UCs; se integra vía inyección de dependencias en el orquestador.
"""
from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Regiones y jurisdicciones
# ---------------------------------------------------------------------------


class Region(str, Enum):
    US_EAST = "us-east"
    US_WEST = "us-west"
    EU_WEST = "eu-west"
    EU_CENTRAL = "eu-central"
    APAC_NORTH = "apac-north"
    APAC_SOUTH = "apac-south"
    LATAM = "latam"
    GLOBAL = "global"


class Jurisdiction(str, Enum):
    GDPR = "gdpr"          # UE / EEA
    CCPA = "ccpa"          # California
    LGPD = "lgpd"          # Brasil
    PIPL = "pipl"          # China
    NIST = "nist"          # EE.UU. fed
    ISO27001 = "iso27001"  # Internacional
    HIPAA = "hipaa"        # Sanidad EE.UU.
    SOC2 = "soc2"


# ---------------------------------------------------------------------------
# Políticas de jurisdicción y residencia
# ---------------------------------------------------------------------------


@dataclass
class JurisdictionRule:
    """Reglas para una jurisdicción/region."""
    data_residency_regions: List[Region] = field(default_factory=list)
    encryption_required: bool = True
    replication_allowed_to: List[Region] = field(default_factory=list)
    replication_requires_consent: bool = False
    retention_days: int = 365
    legal_hold_possible: bool = True
    pii_handling: str = "mask_or_tokenize"  # allow | deny | mask_or_tokenize
    audit_required: bool = True
    requires_dpo_review: bool = False


class JurisdictionPolicy:
    """Mapeo región/jurisdicción → reglas de residencia y compliance."""

    DEFAULT_RULES: Dict[Tuple[Region, Optional[Jurisdiction]], JurisdictionRule] = {
        (Region.EU_WEST, Jurisdiction.GDPR): JurisdictionRule(
            data_residency_regions=[Region.EU_WEST, Region.EU_CENTRAL],
            encryption_required=True,
            replication_allowed_to=[Region.EU_CENTRAL],
            replication_requires_consent=True,
            retention_days=2555,  # 7 años por regulatoria común
            legal_hold_possible=True,
            pii_handling="mask_or_tokenize",
            audit_required=True,
            requires_dpo_review=True,
        ),
        (Region.US_EAST, Jurisdiction.CCPA): JurisdictionRule(
            data_residency_regions=[Region.US_EAST, Region.US_WEST],
            encryption_required=True,
            replication_allowed_to=[Region.US_WEST],
            retention_days=2555,
            pii_handling="allow_with_disclosure",
        ),
        (Region.LATAM, Jurisdiction.LGPD): JurisdictionRule(
            data_residency_regions=[Region.LATAM],
            replication_allowed_to=[Region.US_EAST],
            replication_requires_consent=True,
            retention_days=1825,
        ),
        (Region.APAC_NORTH, Jurisdiction.PIPL): JurisdictionRule(
            data_residency_regions=[Region.APAC_NORTH],
            replication_allowed_to=[],
            retention_days=1095,
            requires_dpo_review=True,
        ),
        (Region.GLOBAL, None): JurisdictionRule(
            data_residency_regions=list(Region),
            replication_allowed_to=list(Region),
            retention_days=2555,
        ),
    }

    def __init__(
        self,
        default_rule: Optional[JurisdictionRule] = None,
        overrides: Optional[Dict[Tuple[Region, Optional[Jurisdiction]], JurisdictionRule]] = None,
    ) -> None:
        self._rules = dict(self.DEFAULT_RULES)
        if overrides:
            self._rules.update(overrides)
        self._default = default_rule or JurisdictionRule()

    def rule_for(self, region: Region, jurisdiction: Optional[Jurisdiction] = None) -> JurisdictionRule:
        key = (region, jurisdiction)
        if key in self._rules:
            return self._rules[key]
        # Fallback por region sin jurisdicción específica
        key_region_only = (region, None)
        if key_region_only in self._rules:
            return self._rules[key_region_only]
        return self._default

    def can_replicate(self, source: Region, target: Region, jurisdiction: Optional[Jurisdiction] = None) -> bool:
        rule = self.rule_for(source, jurisdiction)
        return target in rule.replication_allowed_to or target in rule.data_residency_regions

    def validate_residency(self, artifact_region: Region, jurisdictions: Set[Jurisdiction]) -> bool:
        """Devuelve True si el artefacto reside en alguna región permitida por todas las jurisdicciones."""
        if not jurisdictions:
            return True
        for j in jurisdictions:
            rule = self.rule_for(artifact_region, j)
            if artifact_region not in rule.data_residency_regions:
                return False
        return True


# ---------------------------------------------------------------------------
# Artefactos y linaje
# ---------------------------------------------------------------------------


class ArtifactType(str, Enum):
    MODEL = "model"
    DATASET = "dataset"
    CHECKPOINT = "checkpoint"
    METRICS = "metrics"
    CONFIG = "config"


class ArtifactStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"
    LEGAL_HOLD = "legal_hold"


class ArtifactTier(str, Enum):
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"
    GLACIER = "glacier"


@dataclass
class ArtifactMetadata:
    """Metadatos de un artefacto MLOps versionado."""

    artifact_id: str = field(default_factory=lambda: f"art-{uuid.uuid4().hex[:10]}")
    artifact_type: ArtifactType = ArtifactType.MODEL
    name: str = ""
    version: str = "1.0.0"
    region: Region = Region.GLOBAL
    owner: str = ""
    run_id: str = ""
    parent_artifact_ids: List[str] = field(default_factory=list)
    checksum: str = ""
    signature: str = ""
    size_bytes: int = 0
    status: ArtifactStatus = ArtifactStatus.ACTIVE
    tier: ArtifactTier = ArtifactTier.HOT
    created_at: float = field(default_factory=time.time)
    last_accessed_at: float = field(default_factory=time.time)
    jurisdictions: Set[Jurisdiction] = field(default_factory=set)
    tags: Dict[str, str] = field(default_factory=dict)
    replication_regions: List[Region] = field(default_factory=list)
    lineage: Dict[str, Any] = field(default_factory=dict)

    def compute_checksum(self, content: bytes) -> str:
        self.checksum = hashlib.sha256(content).hexdigest()
        return self.checksum

    def fingerprint(self) -> str:
        payload = f"{self.artifact_id}:{self.version}:{self.region}:{self.checksum}"
        return hashlib.sha256(payload.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type.value,
            "name": self.name,
            "version": self.version,
            "region": self.region.value,
            "owner": self.owner,
            "run_id": self.run_id,
            "parent_artifact_ids": self.parent_artifact_ids,
            "checksum": self.checksum,
            "signature": self.signature,
            "size_bytes": self.size_bytes,
            "status": self.status.value,
            "tier": self.tier.value,
            "created_at": self.created_at,
            "last_accessed_at": self.last_accessed_at,
            "jurisdictions": [j.value for j in self.jurisdictions],
            "tags": self.tags,
            "replication_regions": [r.value for r in self.replication_regions],
            "lineage": self.lineage,
        }


# ---------------------------------------------------------------------------
# Conflictos y resolución
# ---------------------------------------------------------------------------


class ConflictType(str, Enum):
    VERSION_DIVERGENCE = "version_divergence"
    CHECKSUM_MISMATCH = "checksum_mismatch"
    DELETED_ACTIVE = "deleted_active"
    JURISDICTION_VIOLATION = "jurisdiction_violation"
    LINEAGE_BREAK = "lineage_break"


@dataclass
class Conflict:
    conflict_id: str = field(default_factory=lambda: f"conflict-{uuid.uuid4().hex[:10]}")
    artifact_id: str = ""
    conflict_type: ConflictType = ConflictType.VERSION_DIVERGENCE
    regions: List[Region] = field(default_factory=list)
    details: str = ""
    detected_at: float = field(default_factory=time.time)
    resolution: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "artifact_id": self.artifact_id,
            "conflict_type": self.conflict_type.value,
            "regions": [r.value for r in self.regions],
            "details": self.details,
            "detected_at": self.detected_at,
            "resolution": self.resolution,
        }


@dataclass
class ConflictResolution:
    strategy: str = ""  # last_writer_wins, quorum_wins, manual_review, reject
    winner_region: Optional[Region] = None
    winner_artifact: Optional[ArtifactMetadata] = None
    reason: str = ""
    requires_hitl: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy,
            "winner_region": self.winner_region.value if self.winner_region else None,
            "winner_artifact": self.winner_artifact.to_dict() if self.winner_artifact else None,
            "reason": self.reason,
            "requires_hitl": self.requires_hitl,
        }


# ---------------------------------------------------------------------------
# Almacén regional y caché
# ---------------------------------------------------------------------------


class RegionalMetadataStore:
    """Almacén de metadatos de una región con caché local."""

    def __init__(self, region: Region) -> None:
        self.region = region
        self._artifacts: Dict[str, ArtifactMetadata] = {}
        self._cache_hits = 0
        self._cache_misses = 0
        self._last_sync_at: Optional[float] = None

    def put(self, artifact: ArtifactMetadata) -> None:
        self._artifacts[artifact.artifact_id] = artifact

    def get(self, artifact_id: str) -> Optional[ArtifactMetadata]:
        art = self._artifacts.get(artifact_id)
        if art:
            self._cache_hits += 1
        else:
            self._cache_misses += 1
        return art

    def touch(self, artifact_id: str) -> None:
        art = self._artifacts.get(artifact_id)
        if art:
            art.last_accessed_at = time.time()

    def list(self, artifact_type: Optional[ArtifactType] = None) -> List[ArtifactMetadata]:
        if artifact_type is None:
            return list(self._artifacts.values())
        return [a for a in self._artifacts.values() if a.artifact_type == artifact_type]

    def delete(self, artifact_id: str) -> bool:
        art = self._artifacts.get(artifact_id)
        if art and art.status == ArtifactStatus.LEGAL_HOLD:
            return False
        if art:
            art.status = ArtifactStatus.DELETED
            return True
        return False

    def sync_marker(self) -> Optional[float]:
        return self._last_sync_at

    def mark_sync(self) -> None:
        self._last_sync_at = time.time()

    def stats(self) -> Dict[str, Any]:
        return {
            "region": self.region.value,
            "artifacts": len(self._artifacts),
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "last_sync_at": self._last_sync_at,
        }


class RegionalArtifactCache:
    """Caché de artefactos físicos de una región (simulada con LRU en memoria)."""

    def __init__(self, region: Region, max_items: int = 100) -> None:
        self.region = region
        self.max_items = max_items
        self._cache: Dict[str, Any] = {}
        self._order: List[str] = []
        self.hits = 0
        self.misses = 0

    def get(self, artifact_id: str) -> Optional[Any]:
        if artifact_id in self._cache:
            self.hits += 1
            self._order.remove(artifact_id)
            self._order.append(artifact_id)
            return self._cache[artifact_id]
        self.misses += 1
        return None

    def put(self, artifact_id: str, content: Any) -> None:
        if artifact_id in self._cache:
            self._order.remove(artifact_id)
        elif len(self._order) >= self.max_items:
            evicted = self._order.pop(0)
            del self._cache[evicted]
        self._cache[artifact_id] = content
        self._order.append(artifact_id)

    def invalidate(self, artifact_id: str) -> None:
        if artifact_id in self._cache:
            self._order.remove(artifact_id)
            del self._cache[artifact_id]


# ---------------------------------------------------------------------------
# Almacén global / federado
# ---------------------------------------------------------------------------


class GlobalMetadataStore:
    """Registro global federado de artefactos MLOps."""

    def __init__(
        self,
        regions: Optional[List[Region]] = None,
        jurisdiction_policy: Optional[JurisdictionPolicy] = None,
    ) -> None:
        self.jurisdiction_policy = jurisdiction_policy or JurisdictionPolicy()
        self._regions: Dict[Region, RegionalMetadataStore] = {}
        self._caches: Dict[Region, RegionalArtifactCache] = {}
        for r in regions or [Region.GLOBAL]:
            self._regions[r] = RegionalMetadataStore(r)
            self._caches[r] = RegionalArtifactCache(r)
        self._conflicts: List[Conflict] = []
        self._replication_log: List[Dict[str, Any]] = []

    def register_artifact(
        self,
        artifact: ArtifactMetadata,
        content: Optional[bytes] = None,
        replicate_to: Optional[List[Region]] = None,
    ) -> Tuple[ArtifactMetadata, List[Conflict]]:
        """Registra un artefacto en su región y replica a regiones permitidas."""
        conflicts: List[Conflict] = []
        if content is not None:
            artifact.compute_checksum(content)

        # Validar residencia
        if not self.jurisdiction_policy.validate_residency(
            artifact.region, artifact.jurisdictions
        ):
            conflicts.append(Conflict(
                artifact_id=artifact.artifact_id,
                conflict_type=ConflictType.JURISDICTION_VIOLATION,
                regions=[artifact.region],
                details=f"Region {artifact.region.value} no cumple residencia para jurisdicciones {artifact.jurisdictions}",
            ))
            return artifact, conflicts

        # Verificar linaje
        for parent_id in artifact.parent_artifact_ids:
            if not self._find_anywhere(parent_id):
                conflicts.append(Conflict(
                    artifact_id=artifact.artifact_id,
                    conflict_type=ConflictType.LINEAGE_BREAK,
                    regions=[artifact.region],
                    details=f"Parent artifact {parent_id} not found",
                ))

        store = self._regions.get(artifact.region)
        if store is None:
            store = RegionalMetadataStore(artifact.region)
            self._regions[artifact.region] = store
        store.put(artifact)
        if content is not None:
            self._caches[artifact.region].put(artifact.artifact_id, content)

        # Replicación
        targets = replicate_to or []
        allowed = []
        for t in targets:
            if t == artifact.region:
                continue
            ok = True
            for j in artifact.jurisdictions:
                if not self.jurisdiction_policy.can_replicate(artifact.region, t, j):
                    ok = False
                    break
            if ok:
                allowed.append(t)
            else:
                conflicts.append(Conflict(
                    artifact_id=artifact.artifact_id,
                    conflict_type=ConflictType.JURISDICTION_VIOLATION,
                    regions=[artifact.region, t],
                    details=f"Replication {artifact.region.value} -> {t.value} blocked by jurisdiction policy",
                ))

        for t in allowed:
            self._replicate_artifact(artifact, t)

        return artifact, conflicts

    def _find_anywhere(self, artifact_id: str) -> Optional[ArtifactMetadata]:
        for store in self._regions.values():
            art = store.get(artifact_id)
            if art and art.status != ArtifactStatus.DELETED:
                return art
        return None

    def _replicate_artifact(self, source_artifact: ArtifactMetadata, target: Region) -> None:
        if target not in self._regions:
            self._regions[target] = RegionalMetadataStore(target)
            self._caches[target] = RegionalArtifactCache(target)
        replica = ArtifactMetadata(
            artifact_id=source_artifact.artifact_id,
            artifact_type=source_artifact.artifact_type,
            name=source_artifact.name,
            version=source_artifact.version,
            region=target,
            owner=source_artifact.owner,
            run_id=source_artifact.run_id,
            parent_artifact_ids=list(source_artifact.parent_artifact_ids),
            checksum=source_artifact.checksum,
            signature=source_artifact.signature,
            size_bytes=source_artifact.size_bytes,
            status=ArtifactStatus.ACTIVE,
            tier=source_artifact.tier,
            created_at=source_artifact.created_at,
            last_accessed_at=time.time(),
            jurisdictions=set(source_artifact.jurisdictions),
            tags=dict(source_artifact.tags),
            replication_regions=list(source_artifact.replication_regions) + [target],
            lineage=dict(source_artifact.lineage),
        )
        self._regions[target].put(replica)
        cached = self._caches[source_artifact.region].get(source_artifact.artifact_id)
        if cached is not None:
            self._caches[target].put(source_artifact.artifact_id, cached)
        self._replication_log.append({
            "artifact_id": source_artifact.artifact_id,
            "source": source_artifact.region.value,
            "target": target.value,
            "timestamp": time.time(),
        })

    def get_artifact(self, artifact_id: str, region: Region) -> Optional[ArtifactMetadata]:
        store = self._regions.get(region)
        if store is None:
            return None
        return store.get(artifact_id)

    def detect_conflicts(self) -> List[Conflict]:
        """Detecta divergencias entre réplicas."""
        by_id: Dict[str, Dict[Region, ArtifactMetadata]] = {}
        for region, store in self._regions.items():
            for art in store.list():
                by_id.setdefault(art.artifact_id, {})[region] = art

        conflicts: List[Conflict] = []
        for aid, regional in by_id.items():
            # checksum mismatch
            checksums = {art.checksum for art in regional.values() if art.status != ArtifactStatus.DELETED}
            if len(checksums) > 1:
                conflicts.append(Conflict(
                    artifact_id=aid,
                    conflict_type=ConflictType.CHECKSUM_MISMATCH,
                    regions=list(regional.keys()),
                    details=f"Checksums differ across regions: {checksums}",
                ))
            # deleted but active elsewhere
            for r, art in regional.items():
                if art.status == ArtifactStatus.DELETED:
                    for r2, art2 in regional.items():
                        if r2 != r and art2.status == ArtifactStatus.ACTIVE:
                            conflicts.append(Conflict(
                                artifact_id=aid,
                                conflict_type=ConflictType.DELETED_ACTIVE,
                                regions=[r, r2],
                                details=f"Artifact deleted in {r.value} but active in {r2.value}",
                            ))
        self._conflicts.extend(conflicts)
        return conflicts

    def resolve_conflict(
        self,
        artifact_id: str,
        strategy: str = "quorum",
    ) -> ConflictResolution:
        """Resuelve conflictos usando la estrategia indicada."""
        by_region: Dict[Region, ArtifactMetadata] = {}
        for region, store in self._regions.items():
            art = store.get(artifact_id)
            if art:
                by_region[region] = art

        if not by_region:
            return ConflictResolution(
                strategy=strategy,
                reason="Artifact not found in any region",
                requires_hitl=True,
            )

        if strategy == "last_writer_wins":
            winner_region, winner = max(by_region.items(), key=lambda kv: kv[1].last_accessed_at)
            return ConflictResolution(
                strategy=strategy,
                winner_region=winner_region,
                winner_artifact=winner,
                reason="Latest write selected by timestamp",
            )

        if strategy == "quorum":
            checksum_counts: Dict[str, int] = {}
            for art in by_region.values():
                checksum_counts[art.checksum] = checksum_counts.get(art.checksum, 0) + 1
            winner_checksum = max(checksum_counts, key=checksum_counts.get)
            if checksum_counts[winner_checksum] <= len(by_region) / 2:
                return ConflictResolution(
                    strategy=strategy,
                    reason="No quorum reached; requires human review",
                    requires_hitl=True,
                )
            for region, art in by_region.items():
                if art.checksum == winner_checksum:
                    return ConflictResolution(
                        strategy=strategy,
                        winner_region=region,
                        winner_artifact=art,
                        reason=f"Quorum reached for checksum {winner_checksum}",
                    )

        # Fallback: reject / manual review
        return ConflictResolution(
            strategy=strategy,
            reason="Unsupported strategy or no automatic resolution possible",
            requires_hitl=True,
        )

    def list_artifacts(
        self,
        region: Optional[Region] = None,
        artifact_type: Optional[ArtifactType] = None,
    ) -> List[Dict[str, Any]]:
        if region:
            store = self._regions.get(region)
            if store is None:
                return []
            return [a.to_dict() for a in store.list(artifact_type)]
        result = []
        for store in self._regions.values():
            result.extend([a.to_dict() for a in store.list(artifact_type)])
        return result

    def global_stats(self) -> Dict[str, Any]:
        return {
            "regions": [r.value for r in self._regions.keys()],
            "artifacts_per_region": {
                r.value: len(s.list()) for r, s in self._regions.items()
            },
            "conflicts": [c.to_dict() for c in self._conflicts],
            "replication_log_size": len(self._replication_log),
        }


# ---------------------------------------------------------------------------
# Ciclo de vida de artefactos
# ---------------------------------------------------------------------------


@dataclass
class RetentionPolicy:
    artifact_type: ArtifactType = ArtifactType.MODEL
    hot_days: int = 7
    warm_days: int = 30
    cold_days: int = 90
    delete_after_days: int = 365
    legal_hold_tag: str = "legal_hold"


class ArtifactLifecycleManager:
    """Gestiona tiering, retención y garbage collection."""

    def __init__(
        self,
        policies: Optional[List[RetentionPolicy]] = None,
    ) -> None:
        self.policies = {p.artifact_type: p for p in (policies or [])}
        self.default = RetentionPolicy()

    def policy_for(self, artifact_type: ArtifactType) -> RetentionPolicy:
        return self.policies.get(artifact_type, self.default)

    def evaluate_tier(self, artifact: ArtifactMetadata) -> ArtifactTier:
        policy = self.policy_for(artifact.artifact_type)
        age_days = (time.time() - artifact.created_at) / 86400.0
        if age_days <= policy.hot_days:
            return ArtifactTier.HOT
        if age_days <= policy.warm_days:
            return ArtifactTier.WARM
        if age_days <= policy.cold_days:
            return ArtifactTier.COLD
        return ArtifactTier.GLACIER

    def should_delete(self, artifact: ArtifactMetadata) -> bool:
        if artifact.status == ArtifactStatus.LEGAL_HOLD:
            return False
        policy = self.policy_for(artifact.artifact_type)
        age_days = (time.time() - artifact.created_at) / 86400.0
        return age_days > policy.delete_after_days

    def run_gc(self, store: RegionalMetadataStore) -> Tuple[int, int]:
        """Devuelve (transicionados, eliminados)."""
        transitioned = 0
        deleted = 0
        for artifact in list(store.list()):
            new_tier = self.evaluate_tier(artifact)
            if artifact.tier != new_tier:
                artifact.tier = new_tier
                transitioned += 1
            if self.should_delete(artifact):
                if store.delete(artifact.artifact_id):
                    deleted += 1
        return transitioned, deleted

    def apply_legal_hold(self, store: RegionalMetadataStore, artifact_id: str) -> bool:
        art = store.get(artifact_id)
        if art:
            art.status = ArtifactStatus.LEGAL_HOLD
            art.tags["legal_hold"] = "true"
            return True
        return False

    def release_legal_hold(self, store: RegionalMetadataStore, artifact_id: str) -> bool:
        art = store.get(artifact_id)
        if art and art.status == ArtifactStatus.LEGAL_HOLD:
            art.status = ArtifactStatus.ARCHIVED
            art.tags.pop("legal_hold", None)
            return True
        return False


# ---------------------------------------------------------------------------
# Recuperación ante desastres
# ---------------------------------------------------------------------------


@dataclass
class BackupSnapshot:
    snapshot_id: str = field(default_factory=lambda: f"snap-{uuid.uuid4().hex[:10]}")
    region: Region = Region.GLOBAL
    artifact_ids: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    stored_offsite: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "region": self.region.value,
            "artifact_ids": self.artifact_ids,
            "created_at": self.created_at,
            "stored_offsite": self.stored_offsite,
        }


class DisasterRecoveryPlan:
    """RPO/RTO y failover de metadata/artefactos."""

    def __init__(
        self,
        primary_region: Region = Region.US_EAST,
        failover_region: Region = Region.US_WEST,
        rpo_seconds: float = 3600.0,
        rto_seconds: float = 300.0,
    ) -> None:
        self.primary_region = primary_region
        self.failover_region = failover_region
        self.rpo_seconds = rpo_seconds
        self.rto_seconds = rto_seconds
        self._snapshots: Dict[str, BackupSnapshot] = {}
        self._last_backup_at: Optional[float] = None
        self._failed_over = False

    def backup(self, store: GlobalMetadataStore) -> BackupSnapshot:
        snap = BackupSnapshot(region=self.primary_region)
        primary = store._regions.get(self.primary_region)
        if primary:
            snap.artifact_ids = [a.artifact_id for a in primary.list()]
        snap.stored_offsite = True
        self._snapshots[snap.snapshot_id] = snap
        self._last_backup_at = time.time()
        return snap

    def check_rpo(self) -> Tuple[bool, float]:
        if self._last_backup_at is None:
            return False, float("inf")
        lag = time.time() - self._last_backup_at
        return lag <= self.rpo_seconds, lag

    def failover(self) -> Dict[str, Any]:
        self._failed_over = True
        return {
            "old_primary": self.primary_region.value,
            "new_primary": self.failover_region.value,
            "rto_target_seconds": self.rto_seconds,
            "timestamp": time.time(),
        }

    def restore_latest_snapshot(self) -> Optional[BackupSnapshot]:
        if not self._snapshots:
            return None
        return max(self._snapshots.values(), key=lambda s: s.created_at)

    def status(self) -> Dict[str, Any]:
        rpo_ok, lag = self.check_rpo()
        return {
            "primary_region": self.primary_region.value,
            "failover_region": self.failover_region.value,
            "rpo_seconds": self.rpo_seconds,
            "rto_seconds": self.rto_seconds,
            "rpo_ok": rpo_ok,
            "rpo_lag_seconds": lag,
            "last_backup_at": self._last_backup_at,
            "failed_over": self._failed_over,
            "snapshots": len(self._snapshots),
        }
