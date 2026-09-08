"""
UC-162 — Validación operacional de LLMOps.

Ejecuta 16 validaciones que cubren todos los componentes del sistema.
"""

import sys
import os
import random

sys.path.insert(0, os.path.dirname(__file__))


def _generate_balanced(n: int = 20):
    rng = random.Random(42)
    docs = []
    for i in range(n):
        docs.append({
            "id": f"doc_{i:03d}",
            "text": f"Documento {i}.",
            "metadata": {
                "id_documento": f"doc_{i:03d}",
                "fuente": f"src_{rng.randint(1, 5)}",
                "fuente_tipo": rng.choice(["academica", "gubernamental", "corporativa", "crowd"]),
                "fecha_creacion": f"2025-01-01",
                "categoria_tema": "trading",
                "genero_autor": rng.choice(["masculino", "femenino", "no_binario"]),
                "region_geografica": rng.choice(["latam", "europa", "norteamerica", "asia"]),
                "perspectiva_tematica": rng.choice(["tecnica", "legal", "etica", "economica", "social"]),
                "idioma": rng.choice(["es", "en", "es", "en"]),
                "periodo_temporal": rng.choice(["2023", "2024", "2025"]),
                "nivel_confianza": 0.8,
            },
        })
    return docs


def _generate_biased(n: int = 20):
    return [{
        "id": f"doc_{i:03d}",
        "text": f"Doc {i}.",
        "metadata": {
            "id_documento": f"doc_{i:03d}",
            "fuente": "single",
            "fuente_tipo": "corporativa",
            "fecha_creacion": "2025-01-01",
            "categoria_tema": "trading",
            "genero_autor": "masculino",
            "region_geografica": "norteamerica",
            "perspectiva_tematica": "tecnica",
            "idioma": "en",
            "periodo_temporal": "2025",
            "nivel_confianza": 0.9,
        },
    } for i in range(n)]


def validate_logical_schema():
    from logical_data_model import LogicalSchema
    schema = LogicalSchema()
    assert len(schema.required_fields) >= 5
    assert len(schema.bias_thresholds) >= 5
    assert "genero_autor" in schema.bias_thresholds
    yaml_out = schema.to_yaml()
    assert "campos_obligatorios" in yaml_out
    return True


def validate_compute_hash():
    from logical_data_model import compute_hash
    h = compute_hash({"a": 1, "b": 2})
    assert len(h) == 64  # sha256
    h2 = compute_hash({"b": 2, "a": 1})
    assert h == h2  # orden no importa
    return True


def validate_bias_verifier_balanced():
    from bias_verifier import BiasVerifier
    from models_162 import CorpusDocument, DocumentMetadata
    genders = ["masculino", "femenino", "no_binario"]
    regions = ["latam", "europa", "norteamerica", "asia"]
    perspectives = ["tecnica", "legal", "etica", "economica", "social"]
    source_types = ["academica", "gubernamental", "corporativa", "crowd"]
    periods = ["2023", "2024", "2025"]
    languages = ["es", "en", "es", "en"]
    docs = []
    for i in range(30):
        meta = DocumentMetadata(
            id_documento=f"d{i}",
            fuente=f"src_{i % 5}",
            fuente_tipo=source_types[i % len(source_types)],
            fecha_creacion="2025-01-01",
            categoria_tema="trading",
            genero_autor=genders[i % len(genders)],
            region_geografica=regions[i % len(regions)],
            perspectiva_tematica=perspectives[i % len(perspectives)],
            idioma=languages[i % len(languages)],
            periodo_temporal=periods[i % len(periods)],
        )
        docs.append(CorpusDocument(id=f"d{i}", text=f"doc {i}", metadata=meta))
    bv = BiasVerifier()
    report = bv.verify(docs)
    assert report.all_passed
    return True


def validate_bias_verifier_biased():
    from bias_verifier import BiasVerifier
    from models_162 import CorpusDocument, DocumentMetadata
    docs = []
    for i in range(20):
        meta = DocumentMetadata(
            id_documento=f"d{i}",
            fuente="single",
            fuente_tipo="corporativa",
            fecha_creacion="2025-01-01",
            categoria_tema="trading",
            genero_autor="masculino",
            region_geografica="norteamerica",
            perspectiva_tematica="tecnica",
            idioma="en",
            periodo_temporal="2025",
        )
        docs.append(CorpusDocument(id=f"d{i}", text=f"doc {i}", metadata=meta))
    bv = BiasVerifier()
    report = bv.verify(docs)
    assert not report.all_passed
    assert "reject_lot" in report.actions or "flag_for_review" in report.actions
    return True


def validate_lineage_tracker():
    from lineage_tracker import LineageTracker
    lt = LineageTracker()
    n1 = lt.register_ingest("doc1", "texto", source="src")
    n2 = lt.register_clean("doc1", "limpio", n1.hash, script_version="v1.0")
    n3 = lt.register_chunk("chunk1", "doc1", "chunk text", n2.hash)
    n4 = lt.register_embedding("chunk1", [0.1, 0.2], n3.hash)
    assert len(lt.graph.nodes) == 4
    assert len(lt.graph.edges) == 3
    chain = lt.trace_back(n4.hash)
    assert len(chain) == 4
    assert chain[0].stage == "embed"
    assert chain[-1].stage == "ingest"
    return True


def validate_hallucination_detector_clean():
    from hallucination_detector import HallucinationDetector
    hd = HallucinationDetector()
    chunks = ["La política permite cancelar en 30 días.", "El reembolso toma 5 días."]
    response = "La política permite cancelar en 30 días y el reembolso toma 5 días."
    report = hd.detect(response, chunks)
    assert not report.is_hallucination
    assert report.coverage_score > 0.5
    return True


def validate_hallucination_detector_hallucination():
    from hallucination_detector import HallucinationDetector
    hd = HallucinationDetector()
    chunks = ["La política permite cancelar en 30 días."]
    response = "El reembolso es inmediato con bonus del 200% sin límite de tiempo."
    report = hd.detect(response, chunks)
    assert report.is_hallucination or report.severity != "none"
    assert len(report.unsupported_claims) > 0
    return True


def validate_hallucination_empty():
    from hallucination_detector import HallucinationDetector
    hd = HallucinationDetector()
    report = hd.detect("", ["chunk"])
    assert report.is_hallucination
    return True


def validate_prompt_versioning():
    from prompt_versioning import PromptRegistry
    pr = PromptRegistry()
    p1 = pr.register("template v1", version="v1.0", tags=["rag"])
    assert not p1.approved
    approved = pr.approve(p1.id, approved_by="compliance")
    assert approved.approved
    evaluated = pr.evaluate(p1.id, 0.85)
    assert evaluated.evaluation_score == 0.85
    assert len(pr.get_approved()) == 1
    return True


def validate_drift_detector_no_drift():
    from conceptual_drift_detector import ConceptualDriftDetector
    dd = ConceptualDriftDetector()
    dd.set_baseline("spread", ["bid_ask", "bid_ask", "bid_ask", "bid_ask", "credit"])
    report = dd.detect("spread", ["bid_ask", "bid_ask", "bid_ask", "bid_ask", "credit"])
    assert not report.is_drift
    return True


def validate_drift_detector_with_drift():
    from conceptual_drift_detector import ConceptualDriftDetector
    dd = ConceptualDriftDetector()
    dd.set_baseline("spread", ["bid_ask", "bid_ask", "bid_ask", "bid_ask", "credit"])
    report = dd.detect("spread", ["volatilidad", "volatilidad", "volatilidad", "volatilidad", "credit"])
    assert report.is_drift
    assert report.drift_type != "none"
    return True


def validate_observability():
    from observability_162 import ObservabilityManager
    om = ObservabilityManager()
    om.log("INFO", "test message", trace_id="t1")
    om.increment("llmops_test_total")
    om.gauge("llmops_test_gauge", 42.0)
    span = om.start_span("test_span", "t1")
    om.end_span(span)
    prom = om.export_prometheus()
    assert "llmops_test_total" in prom
    assert "llmops_test_gauge" in prom
    summary = om.get_summary()
    assert summary["log_count"] == 1
    return True


def validate_guardian_process_corpus_balanced():
    from llmops_guardian import LLMOpsGuardian
    from models_162 import CorpusDocument, DocumentMetadata
    genders = ["masculino", "femenino", "no_binario"]
    regions = ["latam", "europa", "norteamerica", "asia"]
    perspectives = ["tecnica", "legal", "etica", "economica", "social"]
    source_types = ["academica", "gubernamental", "corporativa", "crowd"]
    periods = ["2023", "2024", "2025"]
    languages = ["es", "en", "es", "en"]
    docs = []
    for i in range(30):
        meta = DocumentMetadata(
            id_documento=f"d{i}",
            fuente=f"src_{i % 5}",
            fuente_tipo=source_types[i % len(source_types)],
            fecha_creacion="2025-01-01",
            categoria_tema="trading",
            genero_autor=genders[i % len(genders)],
            region_geografica=regions[i % len(regions)],
            perspectiva_tematica=perspectives[i % len(perspectives)],
            idioma=languages[i % len(languages)],
            periodo_temporal=periods[i % len(periods)],
        )
        docs.append(CorpusDocument(id=f"d{i}", text=f"doc {i}", metadata=meta))
    g = LLMOpsGuardian()
    result = g.process_corpus(docs, source="trusted")
    assert result.decision == "approve"
    assert result.bias_report["all_passed"]
    return True


def validate_guardian_process_corpus_biased():
    from llmops_guardian import LLMOpsGuardian
    from models_162 import CorpusDocument, DocumentMetadata
    docs = []
    for i in range(20):
        meta = DocumentMetadata(
            id_documento=f"d{i}",
            fuente="single",
            fuente_tipo="corporativa",
            fecha_creacion="2025-01-01",
            categoria_tema="trading",
            genero_autor="masculino",
            region_geografica="norteamerica",
            perspectiva_tematica="tecnica",
            idioma="en",
            periodo_temporal="2025",
        )
        docs.append(CorpusDocument(id=f"d{i}", text=f"doc {i}", metadata=meta))
    g = LLMOpsGuardian()
    result = g.process_corpus(docs, source="unknown")
    assert result.decision in ("reject", "flag")
    assert not result.bias_report["all_passed"]
    return True


def validate_guardian_evaluate_response():
    from llmops_guardian import LLMOpsGuardian
    g = LLMOpsGuardian()
    result = g.evaluate_response(
        response="La política permite cancelar en 30 días.",
        retrieved_chunks=["La política permite cancelar en 30 días."],
    )
    assert result.decision == "approve"
    return True


def validate_guardian_metrics():
    from llmops_guardian import LLMOpsGuardian
    g = LLMOpsGuardian()
    g.process_corpus([], source="test")
    metrics = g.get_metrics()
    assert "llmops_guardian_duration_ms" in metrics
    assert "component=" in metrics
    return True


VALIDATIONS = [
    ("LogicalSchema", validate_logical_schema),
    ("compute_hash", validate_compute_hash),
    ("BiasVerifier balanced", validate_bias_verifier_balanced),
    ("BiasVerifier biased", validate_bias_verifier_biased),
    ("LineageTracker", validate_lineage_tracker),
    ("HallucinationDetector clean", validate_hallucination_detector_clean),
    ("HallucinationDetector hallucination", validate_hallucination_detector_hallucination),
    ("HallucinationDetector empty", validate_hallucination_empty),
    ("PromptVersioning", validate_prompt_versioning),
    ("DriftDetector no drift", validate_drift_detector_no_drift),
    ("DriftDetector with drift", validate_drift_detector_with_drift),
    ("ObservabilityManager", validate_observability),
    ("Guardian process corpus balanced", validate_guardian_process_corpus_balanced),
    ("Guardian process corpus biased", validate_guardian_process_corpus_biased),
    ("Guardian evaluate response", validate_guardian_evaluate_response),
    ("Guardian metrics", validate_guardian_metrics),
]


def main():
    print("=" * 60)
    print("UC-162 — LLMOps Guardian Validación Operacional")
    print("=" * 60)
    passed = 0
    failed = 0
    for name, func in VALIDATIONS:
        try:
            func()
            print(f"  [OK] {name}")
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            failed += 1
    print("-" * 60)
    print(f"Resultado: {passed}/{len(VALIDATIONS)} OK, {failed} failed")
    if failed == 0:
        print("[OK] Todos los procesos están funcionando correctamente.")
    else:
        print("[FAIL] Hay procesos que no funcionan correctamente.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
