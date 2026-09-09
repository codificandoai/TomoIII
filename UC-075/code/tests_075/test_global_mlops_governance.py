"""Tests para global_mlops_governance.py — metadata y artefactos multi-región."""
from __future__ import annotations

import time

import pytest

from global_mlops_governance import (
    ArtifactLifecycleManager,
    ArtifactMetadata,
    ArtifactStatus,
    ArtifactTier,
    ArtifactType,
    BackupSnapshot,
    ConflictType,
    DisasterRecoveryPlan,
    GlobalMetadataStore,
    Jurisdiction,
    JurisdictionPolicy,
    JurisdictionRule,
    Region,
    RegionalMetadataStore,
    RetentionPolicy,
)


# ---------------------------------------------------------------------------
# JurisdictionPolicy
# ---------------------------------------------------------------------------

class TestJurisdictionPolicy:
    def test_gdpr_blocks_replication_outside_eu(self):
        policy = JurisdictionPolicy()
        assert policy.can_replicate(Region.EU_WEST, Region.EU_CENTRAL, Jurisdiction.GDPR)
        assert not policy.can_replicate(Region.EU_WEST, Region.US_EAST, Jurisdiction.GDPR)

    def test_pipl_blocks_all_replication(self):
        policy = JurisdictionPolicy()
        assert not policy.can_replicate(Region.APAC_NORTH, Region.US_EAST, Jurisdiction.PIPL)
        assert not policy.can_replicate(Region.APAC_NORTH, Region.APAC_SOUTH, Jurisdiction.PIPL)

    def test_residency_validation(self):
        policy = JurisdictionPolicy()
        assert policy.validate_residency(Region.EU_WEST, {Jurisdiction.GDPR})
        assert not policy.validate_residency(Region.US_EAST, {Jurisdiction.GDPR})

    def test_custom_override(self):
        overrides = {
            (Region.US_EAST, Jurisdiction.HIPAA): JurisdictionRule(
                data_residency_regions=[Region.US_EAST],
                replication_allowed_to=[Region.US_WEST],
                encryption_required=True,
            )
        }
        policy = JurisdictionPolicy(overrides=overrides)
        assert policy.can_replicate(Region.US_EAST, Region.US_WEST, Jurisdiction.HIPAA)
        assert not policy.can_replicate(Region.US_EAST, Region.EU_WEST, Jurisdiction.HIPAA)


# ---------------------------------------------------------------------------
# GlobalMetadataStore
# ---------------------------------------------------------------------------

class TestGlobalMetadataStore:
    def test_register_artifact_and_replicate(self):
        store = GlobalMetadataStore(regions=[Region.US_EAST, Region.US_WEST])
        art = ArtifactMetadata(
            name="model-v1",
            artifact_type=ArtifactType.MODEL,
            region=Region.US_EAST,
            version="1.0.0",
        )
        registered, conflicts = store.register_artifact(
            art, content=b"model-data", replicate_to=[Region.US_WEST]
        )
        assert not conflicts
        assert registered.checksum
        replica = store.get_artifact(registered.artifact_id, Region.US_WEST)
        assert replica is not None
        assert replica.region == Region.US_WEST

    def test_gdpr_blocks_cross_region_replication(self):
        store = GlobalMetadataStore(regions=[Region.EU_WEST, Region.US_EAST])
        art = ArtifactMetadata(
            name="eu-dataset",
            artifact_type=ArtifactType.DATASET,
            region=Region.EU_WEST,
            jurisdictions={Jurisdiction.GDPR},
        )
        _, conflicts = store.register_artifact(
            art, content=b"eu-data", replicate_to=[Region.US_EAST]
        )
        assert conflicts
        assert any(c.conflict_type == ConflictType.JURISDICTION_VIOLATION for c in conflicts)
        assert store.get_artifact(art.artifact_id, Region.US_EAST) is None

    def test_lineage_break_detected(self):
        store = GlobalMetadataStore(regions=[Region.US_EAST])
        art = ArtifactMetadata(
            name="child-model",
            artifact_type=ArtifactType.MODEL,
            region=Region.US_EAST,
            parent_artifact_ids=["missing-parent"],
        )
        _, conflicts = store.register_artifact(art, content=b"child")
        assert any(c.conflict_type == ConflictType.LINEAGE_BREAK for c in conflicts)

    def test_detect_checksum_mismatch(self):
        store = GlobalMetadataStore(regions=[Region.US_EAST, Region.US_WEST])
        art = ArtifactMetadata(
            name="model-v1",
            artifact_type=ArtifactType.MODEL,
            region=Region.US_EAST,
        )
        registered, _ = store.register_artifact(art, content=b"data", replicate_to=[Region.US_WEST])
        # Modificar checksum de la réplica manualmente
        replica = store.get_artifact(registered.artifact_id, Region.US_WEST)
        replica.checksum = "tampered"
        conflicts = store.detect_conflicts()
        assert any(c.conflict_type == ConflictType.CHECKSUM_MISMATCH for c in conflicts)

    def test_detect_deleted_active_conflict(self):
        store = GlobalMetadataStore(regions=[Region.US_EAST, Region.US_WEST])
        art = ArtifactMetadata(
            name="model-v1",
            artifact_type=ArtifactType.MODEL,
            region=Region.US_EAST,
        )
        registered, _ = store.register_artifact(art, content=b"data", replicate_to=[Region.US_WEST])
        store._regions[Region.US_EAST].delete(registered.artifact_id)
        conflicts = store.detect_conflicts()
        assert any(c.conflict_type == ConflictType.DELETED_ACTIVE for c in conflicts)

    def test_resolve_conflict_last_writer_wins(self):
        store = GlobalMetadataStore(regions=[Region.US_EAST, Region.US_WEST])
        art = ArtifactMetadata(name="m", artifact_type=ArtifactType.MODEL, region=Region.US_EAST)
        registered, _ = store.register_artifact(art, content=b"data", replicate_to=[Region.US_WEST])
        # Simula escritura más reciente en us-west
        time.sleep(0.01)
        store._regions[Region.US_WEST].get(registered.artifact_id).last_accessed_at = time.time()
        resolution = store.resolve_conflict(registered.artifact_id, strategy="last_writer_wins")
        assert resolution.strategy == "last_writer_wins"
        assert resolution.winner_region == Region.US_WEST

    def test_resolve_conflict_quorum(self):
        store = GlobalMetadataStore(regions=[Region.US_EAST, Region.US_WEST, Region.EU_WEST])
        art = ArtifactMetadata(name="m", artifact_type=ArtifactType.MODEL, region=Region.US_EAST)
        registered, _ = store.register_artifact(
            art, content=b"data", replicate_to=[Region.US_WEST, Region.EU_WEST]
        )
        # Todas las réplicas iguales → quorum
        resolution = store.resolve_conflict(registered.artifact_id, strategy="quorum")
        assert not resolution.requires_hitl
        assert resolution.winner_artifact is not None

    def test_resolve_conflict_no_quorum(self):
        store = GlobalMetadataStore(regions=[Region.US_EAST, Region.US_WEST, Region.EU_WEST])
        art = ArtifactMetadata(name="m", artifact_type=ArtifactType.MODEL, region=Region.US_EAST)
        registered, _ = store.register_artifact(
            art, content=b"data", replicate_to=[Region.US_WEST, Region.EU_WEST]
        )
        # Diferenciar checksums para evitar quorum
        store._regions[Region.US_WEST].get(registered.artifact_id).checksum = "a"
        store._regions[Region.EU_WEST].get(registered.artifact_id).checksum = "b"
        resolution = store.resolve_conflict(registered.artifact_id, strategy="quorum")
        assert resolution.requires_hitl

    def test_global_stats(self):
        store = GlobalMetadataStore(regions=[Region.US_EAST])
        art = ArtifactMetadata(name="m", artifact_type=ArtifactType.MODEL, region=Region.US_EAST)
        store.register_artifact(art, content=b"data")
        stats = store.global_stats()
        assert stats["artifacts_per_region"]["us-east"] == 1


# ---------------------------------------------------------------------------
# Regional cache
# ---------------------------------------------------------------------------

class TestRegionalArtifactCache:
    def test_get_does_not_mutate_last_accessed(self):
        from global_mlops_governance import RegionalMetadataStore
        store = RegionalMetadataStore(Region.US_EAST)
        art = ArtifactMetadata(name="x", artifact_type=ArtifactType.MODEL, region=Region.US_EAST, last_accessed_at=1.0)
        store.put(art)
        got = store.get(art.artifact_id)
        assert got is not None
        assert got.last_accessed_at == 1.0

    def test_lru_eviction(self):
        from global_mlops_governance import RegionalArtifactCache
        cache = RegionalArtifactCache(Region.US_EAST, max_items=2)
        cache.put("a", b"1")
        cache.put("b", b"2")
        cache.put("c", b"3")
        assert cache.get("a") is None
        assert cache.get("b") == b"2"
        assert cache.get("c") == b"3"


# ---------------------------------------------------------------------------
# Lifecycle manager
# ---------------------------------------------------------------------------

class TestArtifactLifecycleManager:
    def test_tiering_hot_to_glacier(self):
        from global_mlops_governance import RegionalMetadataStore
        policy = RetentionPolicy(artifact_type=ArtifactType.MODEL, hot_days=1, warm_days=2, cold_days=3, delete_after_days=100)
        manager = ArtifactLifecycleManager(policies=[policy])
        store = RegionalMetadataStore(Region.US_EAST)
        old = ArtifactMetadata(
            name="old-model",
            artifact_type=ArtifactType.MODEL,
            region=Region.US_EAST,
            created_at=time.time() - 86400 * 4,  # 4 días
        )
        store.put(old)
        transitioned, _ = manager.run_gc(store)
        assert transitioned == 1
        assert old.tier == ArtifactTier.GLACIER

    def test_glacier_after_cold_period(self):
        policy = RetentionPolicy(artifact_type=ArtifactType.MODEL, hot_days=1, warm_days=2, cold_days=3, delete_after_days=100)
        manager = ArtifactLifecycleManager(policies=[policy])
        store = RegionalMetadataStore(Region.US_EAST)
        very_old = ArtifactMetadata(
            name="very-old",
            artifact_type=ArtifactType.MODEL,
            region=Region.US_EAST,
            created_at=time.time() - 86400 * 5,
        )
        store.put(very_old)
        manager.run_gc(store)
        assert very_old.tier == ArtifactTier.GLACIER

    def test_legal_hold_blocks_delete(self):
        policy = RetentionPolicy(artifact_type=ArtifactType.MODEL, delete_after_days=0)
        manager = ArtifactLifecycleManager(policies=[policy])
        store = RegionalMetadataStore(Region.US_EAST)
        art = ArtifactMetadata(name="held", artifact_type=ArtifactType.MODEL, region=Region.US_EAST)
        store.put(art)
        manager.apply_legal_hold(store, art.artifact_id)
        transitioned, deleted = manager.run_gc(store)
        assert deleted == 0
        assert art.status == ArtifactStatus.LEGAL_HOLD


# ---------------------------------------------------------------------------
# Disaster recovery
# ---------------------------------------------------------------------------

class TestDisasterRecoveryPlan:
    def test_backup_and_restore(self):
        store = GlobalMetadataStore(regions=[Region.US_EAST])
        art = ArtifactMetadata(name="m", artifact_type=ArtifactType.MODEL, region=Region.US_EAST)
        store.register_artifact(art, content=b"data")
        dr = DisasterRecoveryPlan(primary_region=Region.US_EAST, failover_region=Region.US_WEST)
        snap = dr.backup(store)
        assert snap.stored_offsite
        latest = dr.restore_latest_snapshot()
        assert latest is not None
        assert latest.snapshot_id == snap.snapshot_id

    def test_rpo_check(self):
        dr = DisasterRecoveryPlan(rpo_seconds=60)
        assert not dr.check_rpo()[0]
        dr.backup(GlobalMetadataStore())
        assert dr.check_rpo()[0]

    def test_failover(self):
        dr = DisasterRecoveryPlan(primary_region=Region.US_EAST, failover_region=Region.US_WEST)
        result = dr.failover()
        assert result["new_primary"] == "us-west"
        assert dr.status()["failed_over"]


# ---------------------------------------------------------------------------
# Integration with orchestrator concept (API-level tested separately)
# ---------------------------------------------------------------------------

class TestGlobalMLOpsIntegration:
    def test_register_dataset_with_parent_lineage(self):
        store = GlobalMetadataStore(regions=[Region.US_EAST, Region.EU_WEST])
        dataset = ArtifactMetadata(
            name="raw-dataset",
            artifact_type=ArtifactType.DATASET,
            region=Region.US_EAST,
        )
        registered_ds, _ = store.register_artifact(dataset, content=b"raw")
        model = ArtifactMetadata(
            name="model",
            artifact_type=ArtifactType.MODEL,
            region=Region.US_EAST,
            parent_artifact_ids=[registered_ds.artifact_id],
        )
        registered_model, conflicts = store.register_artifact(model, content=b"model")
        assert not conflicts
        assert registered_model.parent_artifact_ids == [registered_ds.artifact_id]
