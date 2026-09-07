"""
UC-328 — Tests unitarios e integración para ORQUESTA-R.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from orquesta_models import (
    OrquestaConfig, Budget, Source, Subquery, PartialResult,
    ResolvedFact, ExecutionMetrics, OrquestaResult, CacheEntry,
    ContextVersion, HealthStatus, ExecutionVerdict, SubqueryStatus,
    SourceType, PrivacyPolicy,
)
from source_registry import SourceRegistry
from schema_federation import SchemaFederation
from query_router import QueryRouter
from cache_manager import CacheManager
from cost_latency_manager import CostLatencyManager
from conflict_resolver import ConflictResolver
from privacy_compliance import PrivacyComplianceManager
from fault_tolerance import FaultToleranceManager
from load_balancer import LoadBalancer
from context_manager import ContextManager
from observability_328 import ObservabilityManager
from orchestrator import OrquestaREngine


# ═══════════════════════════════════════════════════════════════════════════
# MODELOS
# ═══════════════════════════════════════════════════════════════════════════

class TestModels:
    def test_orquesta_config_default(self):
        cfg = OrquestaConfig()
        assert cfg.cache_enabled is True
        assert cfg.budget.max_cost > 0

    def test_source_creation(self):
        s = Source(name="x", source_type=SourceType.API)
        assert s.source_id != ""
        assert s.to_dict()["name"] == "x"

    def test_subquery(self):
        sq = Subquery(text="q")
        assert sq.subquery_id != ""

    def test_cache_entry_expired(self):
        import time
        ce = CacheEntry(key="k", value="v", ttl_seconds=-1, created_at=time.time())
        assert ce.is_expired is True

    def test_execution_metrics_reliability(self):
        m = ExecutionMetrics(subqueries_total=4, subqueries_successful=3)
        assert m.reliability == 0.75

    def test_orquesta_result(self):
        r = OrquestaResult(query="test")
        assert r.trace_id != ""


# ═══════════════════════════════════════════════════════════════════════════
# REGISTRO DE FUENTES
# ═══════════════════════════════════════════════════════════════════════════

class TestSourceRegistry:
    def test_register_from_dict(self):
        r = SourceRegistry()
        s = r.register_from_dict({
            "name": "Test",
            "source_type": "api",
            "cost_per_call": 0.1,
            "capabilities": ["news"],
        })
        assert s.name == "Test"
        assert len(r.list_sources()) == 1

    def test_find_for_subquery(self):
        r = SourceRegistry()
        r.register_from_dict({
            "name": "NewsAPI", "source_type": "api",
            "capabilities": ["news"], "tags": ["financial"],
        })
        found = r.find_for_subquery("financial news", ["news"])
        assert len(found) == 1

    def test_connector_registration(self):
        r = SourceRegistry()
        s = r.register_from_dict({"name": "A", "source_type": "api"})
        r.register_connector(s.source_id, lambda q, m: "x")
        assert r.get_connector(s.source_id) is not None


# ═══════════════════════════════════════════════════════════════════════════
# FEDERACIÓN DE ESQUEMAS
# ═══════════════════════════════════════════════════════════════════════════

class TestSchemaFederation:
    def test_normalize_dict(self):
        sf = SchemaFederation()
        src = Source(name="s", source_type=SourceType.API)
        sf.register_adapter(src.source_id, {"content": "text", "category": "type"})
        out = sf.normalize(src, {"text": "hello", "type": "greet"})
        assert out["content"] == "hello"

    def test_normalize_string(self):
        sf = SchemaFederation()
        src = Source(name="s", source_type=SourceType.API)
        out = sf.normalize(src, "hello")
        assert out["content"] == "hello"

    def test_build_adapter(self):
        sf = SchemaFederation()
        src = Source(name="s", source_type=SourceType.API, schema={"text": "str", "type": "str"})
        adapter = sf.build_adapter_from_schema(src)
        assert "content" in adapter


# ═══════════════════════════════════════════════════════════════════════════
# ROUTER
# ═══════════════════════════════════════════════════════════════════════════

class TestQueryRouter:
    def test_decompose(self):
        r = QueryRouter()
        subs = r.decompose("latest stock news and sentiment")
        assert len(subs) >= 1

    def test_select_sources(self):
        r = QueryRouter()
        sources = [
            Source(name="s1", source_type=SourceType.API, cost_per_call=0.1, reliability=0.9, base_latency_ms=100),
            Source(name="s2", source_type=SourceType.API, cost_per_call=0.5, reliability=0.5, base_latency_ms=200),
        ]
        ordered = r.select_sources(Subquery(text="test"), sources)
        assert ordered[0].name == "s1"


# ═══════════════════════════════════════════════════════════════════════════
# CACHÉ
# ═══════════════════════════════════════════════════════════════════════════

class TestCacheManager:
    def test_hit_and_miss(self):
        c = CacheManager()
        c.set("q", "s1", {"x": 1})
        assert c.get("q", "s1")["x"] == 1
        assert c.get("other", "s1") is None

    def test_statistics(self):
        c = CacheManager()
        c.set("q", "s1", {"x": 1})
        c.get("q", "s1")
        stats = c.get_statistics()
        assert stats["total_hits"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# COSTO/LATENCIA
# ═══════════════════════════════════════════════════════════════════════════

class TestCostLatencyManager:
    def test_estimate(self):
        mgr = CostLatencyManager(Budget(max_cost=10.0, max_latency_ms=1000.0))
        src = Source(cost_per_call=0.5, base_latency_ms=100.0)
        sub = Subquery(text="test")
        est = mgr.estimate(src, sub)
        assert est["estimated_cost"] > 0

    def test_can_afford(self):
        mgr = CostLatencyManager(Budget(max_cost=1.0, max_latency_ms=1000.0))
        assert mgr.can_afford(0.5, 100.0)

    def test_record_actual(self):
        mgr = CostLatencyManager(Budget(max_cost=10.0, max_latency_ms=1000.0))
        mgr.record_actual("s1", 0.1, 100.0, success=True)
        assert mgr.get_statistics()["spent_cost"] == 0.1


# ═══════════════════════════════════════════════════════════════════════════
# RESOLUCIÓN DE CONFLICTOS
# ═══════════════════════════════════════════════════════════════════════════

class TestConflictResolver:
    def test_resolve_numeric(self):
        r = ConflictResolver()
        partials = [
            PartialResult(data=10.0, confidence=0.9, source_id="s1"),
            PartialResult(data=12.0, confidence=0.7, source_id="s2"),
        ]
        resolved = r.resolve("price", partials)
        assert 10.0 <= resolved.value <= 12.0

    def test_resolve_categorical(self):
        r = ConflictResolver()
        partials = [
            PartialResult(data="buy", confidence=0.9, source_id="s1"),
            PartialResult(data="buy", confidence=0.6, source_id="s2"),
        ]
        resolved = r.resolve("signal", partials)
        assert resolved.value == "buy"


# ═══════════════════════════════════════════════════════════════════════════
# PRIVACIDAD
# ═══════════════════════════════════════════════════════════════════════════

class TestPrivacyCompliance:
    def test_detect_email(self):
        mgr = PrivacyComplianceManager()
        findings = mgr.detect_sensitive("contact a@b.com")
        assert any(f["type"] == "email" for f in findings)

    def test_apply_gdpr(self):
        mgr = PrivacyComplianceManager(active_policies=[PrivacyPolicy.GDPR])
        text = "email a@b.com"
        out = mgr.apply_policy(text, PrivacyPolicy.GDPR)
        assert "a@b.com" not in out

    def test_filter_sources(self):
        mgr = PrivacyComplianceManager(active_policies=[PrivacyPolicy.GDPR])
        src = Source(name="s", source_type=SourceType.API, metadata={"regions_blocked": ["EU"]})
        allowed = mgr.filter_sources_by_policy([src], "EU")
        assert len(allowed) == 0


# ═══════════════════════════════════════════════════════════════════════════
# TOLERANCIA A FALLOS
# ═══════════════════════════════════════════════════════════════════════════

class TestFaultTolerance:
    def test_circuit_breaker(self):
        ft = FaultToleranceManager(failure_threshold=2, circuit_breaker_seconds=1.0)
        ft.record_failure("s1")
        ft.record_failure("s1")
        assert not ft.is_available("s1")

    def test_success_resets_failures(self):
        ft = FaultToleranceManager(failure_threshold=2)
        ft.record_failure("s1")
        ft.record_success("s1", 100.0)
        ft.record_failure("s1")
        assert ft.is_available("s1")

    def test_execute_with_retry(self):
        ft = FaultToleranceManager(max_retries=1)
        counter = {"n": 0}
        def op():
            counter["n"] += 1
            if counter["n"] < 2:
                raise RuntimeError("fail")
            return "ok"
        result, success, attempts = ft.execute_with_retry("s1", op)
        assert success is True
        assert result == "ok"


# ═══════════════════════════════════════════════════════════════════════════
# BALANCEADOR DE CARGA
# ═══════════════════════════════════════════════════════════════════════════

class TestLoadBalancer:
    def test_select_best(self):
        lb = LoadBalancer()
        s1 = Source(name="s1", source_type=SourceType.API, reliability=0.9, cost_per_call=0.1)
        s2 = Source(name="s2", source_type=SourceType.API, reliability=0.5, cost_per_call=0.5)
        best = lb.select_best([s1, s2])
        assert best.name == "s1"

    def test_overload_rebalance(self):
        lb = LoadBalancer()
        s1 = Source(name="s1", source_type=SourceType.API)
        s2 = Source(name="s2", source_type=SourceType.API)
        lb.assign(s1.source_id)
        alt = lb.rebalance_tasks(s1.source_id, [s1, s2], threshold=1)
        assert alt is not None


# ═══════════════════════════════════════════════════════════════════════════
# CONTEXTO PERSISTENTE
# ═══════════════════════════════════════════════════════════════════════════

class TestContextManager:
    def test_update_and_load(self):
        cm = ContextManager()
        cm.update({"k": "v"})
        assert cm.get("k") == "v"

    def test_versioning(self):
        cm = ContextManager()
        v1 = cm.update({"k": "v1"})
        v2 = cm.update({"k": "v2"})
        assert v2.parent_version_id == v1.version_id


# ═══════════════════════════════════════════════════════════════════════════
# OBSERVABILIDAD
# ═══════════════════════════════════════════════════════════════════════════

class TestObservability:
    def test_span(self):
        obs = ObservabilityManager()
        span = obs.start_span("op")
        obs.end_span(span.span_id)
        assert len(obs.get_spans(trace_id=span.trace_id)) == 1

    def test_log(self):
        obs = ObservabilityManager()
        obs.log("INFO", "test")
        assert len(obs.get_logs()) == 1


# ═══════════════════════════════════════════════════════════════════════════
# ORQUESTADOR
# ═══════════════════════════════════════════════════════════════════════════

class TestOrchestrator:
    def test_basic_execution(self):
        engine = OrquestaREngine()
        engine.register_source({
            "name": "TestSource",
            "source_type": "api",
            "cost_per_call": 0.1,
            "base_latency_ms": 50.0,
            "capabilities": ["general"],
        }, connector=lambda q, m: {"content": f"answer to {q}", "confidence": 0.8})
        result = engine.execute("hello", user_region="global")
        assert result.verdict is not None
        assert result.duration_ms >= 0

    def test_execution_with_conflicts(self):
        engine = OrquestaREngine()

        def c1(q, m):
            return {"value": 10.0, "confidence": 0.8}

        def c2(q, m):
            return {"value": 12.0, "confidence": 0.7}

        engine.register_source({
            "name": "S1", "source_type": "api",
            "cost_per_call": 0.1, "capabilities": ["general"],
        }, connector=c1)
        engine.register_source({
            "name": "S2", "source_type": "api",
            "cost_per_call": 0.1, "capabilities": ["general"],
        }, connector=c2)

        result = engine.execute("price estimate", user_region="global")
        assert len(result.resolved_facts) > 0

    def test_source_excluded_by_privacy(self):
        engine = OrquestaREngine()
        engine.register_source({
            "name": "EUBlocked", "source_type": "api",
            "cost_per_call": 0.1, "capabilities": ["general"],
            "metadata": {"regions_blocked": ["EU"]},
        }, connector=lambda q, m: "x")
        result = engine.execute("test", user_region="EU")
        assert result is not None

    def test_statistics(self):
        engine = OrquestaREngine()
        stats = engine.get_statistics()
        assert "sources" in stats


# ═══════════════════════════════════════════════════════════════════════════
# API FLASK
# ═══════════════════════════════════════════════════════════════════════════

class TestAPI:
    @pytest.fixture
    def client(self):
        from api_328 import app
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_schema(self, client):
        resp = client.get("/api/v1/schema")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "input_cards" in data

    def test_execute(self, client):
        resp = client.post("/api/v1/orquesta/execute", json={
            "query": "test",
            "context": "",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "verdict" in data

    def test_execute_missing_query(self, client):
        resp = client.post("/api/v1/orquesta/execute", json={})
        assert resp.status_code == 400

    def test_register_source(self, client):
        resp = client.post("/api/v1/orquesta/sources", json={
            "source": {"name": "Test", "source_type": "api"}
        })
        assert resp.status_code == 200

    def test_stats(self, client):
        resp = client.get("/api/v1/orquesta/stats")
        assert resp.status_code == 200
