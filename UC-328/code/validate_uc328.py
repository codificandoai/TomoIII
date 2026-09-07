"""
UC-328 — Validación operacional de ORQUESTA-R.

Verifica los 10 procesos principales:
1. Modelos de datos y configuración.
2. Registro de fuentes.
3. Federación de esquemas.
4. Router de consultas.
5. Caché.
6. Costo y latencia.
7. Resolución de conflictos.
8. Privacidad y cumplimiento.
9. Tolerancia a fallos.
10. Orquestador completo.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))


def validate_models():
    """Valida modelos de datos."""
    from orquesta_models import (
        OrquestaConfig, Budget, Source, Subquery, PartialResult,
        ResolvedFact, ExecutionMetrics, OrquestaResult, CacheEntry,
        SourceType,
    )
    config = OrquestaConfig()
    assert config.budget.max_cost > 0
    source = Source(name="test", source_type=SourceType.API)
    sub = Subquery(text="test")
    partial = PartialResult(subquery_id=sub.subquery_id, source_id=source.source_id)
    resolved = ResolvedFact(key="k", value="v", confidence=0.9)
    metrics = ExecutionMetrics()
    assert metrics.reliability == 0.0
    result = OrquestaResult(query="test")
    assert result.trace_id != ""
    return True


def validate_source_registry():
    """Valida registro de fuentes."""
    from source_registry import SourceRegistry
    from orquesta_models import Source

    registry = SourceRegistry()
    src = registry.register_from_dict({
        "name": "Test API",
        "source_type": "api",
        "cost_per_call": 0.1,
        "capabilities": ["news"],
        "tags": ["test"],
    })
    assert src.source_id != ""
    assert len(registry.list_sources()) == 1
    found = registry.find_for_subquery("latest news", ["news"])
    assert len(found) == 1
    return True


def validate_schema_federation():
    """Valida federación de esquemas."""
    from schema_federation import SchemaFederation
    from orquesta_models import Source, SourceType

    sf = SchemaFederation()
    src = Source(name="test", source_type=SourceType.API)
    sf.register_adapter(src.source_id, {"content": "text", "category": "type"})
    data = {"text": "hello", "type": "greeting", "extra": 123}
    normalized = sf.normalize(src, data)
    assert "content" in normalized
    return True


def validate_query_router():
    """Valida router de consultas."""
    from query_router import QueryRouter

    router = QueryRouter()
    subs = router.decompose("latest stock news and sentiment")
    assert len(subs) >= 1
    return True


def validate_cache():
    """Valida caché."""
    from cache_manager import CacheManager

    cache = CacheManager(default_ttl_seconds=60)
    cache.set("q1", "s1", {"data": "value"})
    hit = cache.get("q1", "s1")
    assert hit is not None
    assert hit["data"] == "value"
    miss = cache.get("q2", "s1")
    assert miss is None
    return True


def validate_cost_latency():
    """Valida gestión de costo y latencia."""
    from cost_latency_manager import CostLatencyManager
    from orquesta_models import Source, Subquery, Budget

    mgr = CostLatencyManager(Budget(max_cost=10.0, max_latency_ms=1000.0))
    src = Source(cost_per_call=0.5, base_latency_ms=100.0)
    sub = Subquery(text="test")
    est = mgr.estimate(src, sub)
    assert est["estimated_cost"] > 0
    assert mgr.can_afford(est["estimated_cost"], est["estimated_latency_ms"])
    return True


def validate_conflict_resolver():
    """Valida resolución de conflictos."""
    from conflict_resolver import ConflictResolver
    from orquesta_models import PartialResult

    resolver = ConflictResolver()
    partials = [
        PartialResult(subquery_id="q1", source_id="s1", data=10.0, confidence=0.9),
        PartialResult(subquery_id="q1", source_id="s2", data=12.0, confidence=0.7),
    ]
    resolved = resolver.resolve("price", partials)
    assert resolved.value is not None
    return True


def validate_privacy():
    """Valida privacidad y cumplimiento."""
    from privacy_compliance import PrivacyComplianceManager
    from orquesta_models import PrivacyPolicy

    mgr = PrivacyComplianceManager(active_policies=[PrivacyPolicy.GDPR])
    text = "Contact john@example.com for details"
    anonymized = mgr.apply_policy(text, PrivacyPolicy.GDPR)
    assert "john@example.com" not in anonymized
    findings = mgr.detect_sensitive("SSN 123-45-6789")
    assert len(findings) >= 1
    return True


def validate_fault_tolerance():
    """Valida tolerancia a fallos."""
    from fault_tolerance import FaultToleranceManager

    ft = FaultToleranceManager(failure_threshold=2, circuit_breaker_seconds=1.0)
    assert ft.is_available("src1")
    ft.record_failure("src1")
    ft.record_failure("src1")
    assert not ft.is_available("src1")
    return True


def validate_orchestrator():
    """Valida orquestador completo."""
    from orchestrator import OrquestaREngine
    from orquesta_models import OrquestaConfig, Budget

    def connector(q, meta):
        return {"content": f"answer to {q}", "confidence": 0.8}

    config = OrquestaConfig(budget=Budget(max_cost=10.0, max_latency_ms=5000.0))
    engine = OrquestaREngine(config=config)
    src = engine.register_source({
        "name": "TestSource",
        "source_type": "api",
        "cost_per_call": 0.1,
        "base_latency_ms": 50.0,
        "capabilities": ["general"],
    }, connector=connector)

    result = engine.execute("test query", user_region="EU")
    assert result is not None
    assert result.verdict is not None
    assert result.duration_ms >= 0
    return True


def main():
    """Ejecuta todas las validaciones."""
    print("=" * 70)
    print("UC-328 — Validación Operacional ORQUESTA-R")
    print("=" * 70)

    validations = [
        ("Modelos de datos y configuración", validate_models),
        ("Registro de fuentes", validate_source_registry),
        ("Federación de esquemas", validate_schema_federation),
        ("Router de consultas", validate_query_router),
        ("Caché", validate_cache),
        ("Costo y latencia", validate_cost_latency),
        ("Resolución de conflictos", validate_conflict_resolver),
        ("Privacidad y cumplimiento", validate_privacy),
        ("Tolerancia a fallos", validate_fault_tolerance),
        ("Orquestador completo", validate_orchestrator),
    ]

    all_ok = True
    for name, fn in validations:
        try:
            result = fn()
            status = "[OK]" if result else "[FAIL]"
            if not result:
                all_ok = False
        except Exception as e:
            status = "[FAIL]"
            all_ok = False
            print(f"  {status} {name}: {e}")
            continue
        print(f"  {status} {name}")

    print("=" * 70)
    if all_ok:
        print("  Todos los 10 procesos están funcionando correctamente.")
    else:
        print("  ALGUNOS PROCESOS FALLARON.")
        sys.exit(1)


if __name__ == "__main__":
    main()
