"""
UC-162 — Tests unitarios y de integración para LLMOps Guardian.

Cubre:
- Modelado lógico (LogicalSchema, compute_hash).
- Verificación de sesgo (BiasVerifier).
- Linaje semántico (LineageTracker).
- Detección de hallucination (HallucinationDetector).
- Versionado de prompts (PromptRegistry).
- Drift conceptual (ConceptualDriftDetector).
- Observabilidad (ObservabilityManager).
- Guardian orquestador (LLMOpsGuardian).
- API REST (api_162).
- Integración end-to-end.
"""

import sys
import os
import random
import json

import pytest

# Asegurar path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models_162 import (
    LLMOpsConfig,
    CorpusDocument,
    DocumentMetadata,
    BiasCheck,
    BiasReport,
    LineageNode,
    LineageGraph,
    HallucinationReport,
    DriftReport,
    PromptVersion,
    LLMOpsResult,
    LLMOpsDecision,
    BiasAction,
    HallucinationSeverity,
    DriftType,
    LineageStage,
)
from logical_data_model import LogicalSchema, compute_hash, document_to_dict
from bias_verifier import BiasVerifier
from lineage_tracker import LineageTracker
from hallucination_detector import HallucinationDetector
from prompt_versioning import PromptRegistry
from conceptual_drift_detector import ConceptualDriftDetector
from observability_162 import ObservabilityManager
from llmops_guardian import LLMOpsGuardian


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_doc(
    doc_id: str,
    genero: str = "masculino",
    region: str = "latam",
    perspectiva: str = "tecnica",
    fuente_tipo: str = "academica",
    idioma: str = "es",
    periodo: str = "2025",
) -> CorpusDocument:
    meta = DocumentMetadata(
        id_documento=doc_id,
        fuente=f"src_{doc_id}",
        fuente_tipo=fuente_tipo,
        fecha_creacion=f"{periodo}-01-01",
        categoria_tema="trading",
        genero_autor=genero,
        region_geografica=region,
        perspectiva_tematica=perspectiva,
        idioma=idioma,
        periodo_temporal=periodo,
        nivel_confianza=0.8,
    )
    return CorpusDocument(id=doc_id, text=f"Documento {doc_id}", metadata=meta)


def _balanced_corpus(n: int = 30) -> list:
    """Genera un corpus determinístico balanceado con representación garantizada."""
    genders = ["masculino", "femenino", "no_binario"]
    regions = ["latam", "europa", "norteamerica", "asia"]
    perspectives = ["tecnica", "legal", "etica", "economica", "social"]
    source_types = ["academica", "gubernamental", "corporativa", "crowd"]
    periods = ["2023", "2024", "2025"]
    languages = ["es", "en", "es", "en"]
    docs = []
    for i in range(n):
        docs.append(_make_doc(
            f"d{i:03d}",
            genero=genders[i % len(genders)],
            region=regions[i % len(regions)],
            perspectiva=perspectives[i % len(perspectives)],
            fuente_tipo=source_types[i % len(source_types)],
            idioma=languages[i % len(languages)],
            periodo=periods[i % len(periods)],
        ))
    return docs


def _biased_corpus(n: int = 20) -> list:
    return [
        _make_doc(
            f"d{i:03d}",
            genero="masculino",
            region="norteamerica",
            perspectiva="tecnica",
            fuente_tipo="corporativa",
            idioma="en",
            periodo="2025",
        )
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Tests: Modelado lógico
# ---------------------------------------------------------------------------

class TestLogicalSchema:
    def test_schema_creation(self):
        schema = LogicalSchema()
        assert schema.version == "2.1"
        assert len(schema.required_fields) >= 5
        assert "id_documento" in schema.required_fields

    def test_bias_thresholds(self):
        schema = LogicalSchema()
        assert "genero_autor" in schema.bias_thresholds
        assert "region_geografica" in schema.bias_thresholds
        assert "perspectiva_tematica" in schema.bias_thresholds
        assert schema.bias_thresholds["genero_autor"].max_dominance == 0.70

    def test_validate_structure_ok(self):
        schema = LogicalSchema()
        doc = _make_doc("d1")
        issues = schema.validate_structure(doc)
        assert len(issues) == 0

    def test_validate_structure_missing_fields(self):
        schema = LogicalSchema()
        doc = CorpusDocument(id="d1", text="text", metadata=DocumentMetadata())
        issues = schema.validate_structure(doc)
        assert len(issues) > 0

    def test_to_dict(self):
        schema = LogicalSchema()
        d = schema.to_dict()
        assert "version" in d
        assert "bias_thresholds" in d
        assert "lineage_stages" in d

    def test_to_yaml(self):
        schema = LogicalSchema()
        y = schema.to_yaml()
        assert "campos_obligatorios" in y
        assert "metadatos_gobernanza" in y

    def test_compute_hash_deterministic(self):
        h1 = compute_hash({"a": 1, "b": 2})
        h2 = compute_hash({"b": 2, "a": 1})
        assert h1 == h2

    def test_compute_hash_different(self):
        h1 = compute_hash({"a": 1})
        h2 = compute_hash({"a": 2})
        assert h1 != h2

    def test_compute_hash_sha256_length(self):
        h = compute_hash({"x": 1})
        assert len(h) == 64


# ---------------------------------------------------------------------------
# Tests: Bias Verifier
# ---------------------------------------------------------------------------

class TestBiasVerifier:
    def test_balanced_corpus_passes(self):
        bv = BiasVerifier()
        docs = _balanced_corpus(30)
        report = bv.verify(docs)
        assert report.all_passed
        assert len(report.checks) >= 5

    def test_biased_corpus_fails(self):
        bv = BiasVerifier()
        docs = _biased_corpus(20)
        report = bv.verify(docs)
        assert not report.all_passed
        assert len(report.actions) > 0

    def test_biased_corpus_reject_action(self):
        bv = BiasVerifier()
        docs = _biased_corpus(20)
        report = bv.verify(docs)
        # region_geografica 100% norteamerica → reject_lot
        assert "reject_lot" in report.actions

    def test_metrics_computed(self):
        bv = BiasVerifier()
        docs = _balanced_corpus(30)
        report = bv.verify(docs)
        assert "entropia_shannon_regiones" in report.metrics
        assert "disparidad_genero" in report.metrics
        assert "entropia_shannon_perspectivas" in report.metrics

    def test_insufficient_documents(self):
        bv = BiasVerifier()
        docs = [_make_doc("d1")]
        report = bv.verify(docs)
        assert report.all_passed  # no hay suficientes docs para verificar
        assert len(report.actions) > 0

    def test_dominance_calculation(self):
        bv = BiasVerifier()
        docs = _biased_corpus(20)
        report = bv.verify(docs)
        genero_check = [c for c in report.checks if c.field_name == "genero_autor"][0]
        assert genero_check.dominance == 1.0  # 100% masculino
        assert not genero_check.passed

    def test_perspective_representation(self):
        bv = BiasVerifier()
        docs = _biased_corpus(20)
        report = bv.verify(docs)
        persp_check = [
            c for c in report.checks
            if c.field_name == "perspectiva_tematica_representation"
        ][0]
        assert not persp_check.passed
        assert "enrich_with_complementary_sources" in persp_check.action

    def test_shannon_entropy(self):
        entropy = BiasVerifier._shannon_entropy(["a", "a", "b", "b"])
        assert entropy == 1.0  # 1 bit de entropía para 2 valores uniformes

    def test_shannon_entropy_single_value(self):
        entropy = BiasVerifier._shannon_entropy(["a", "a", "a"])
        assert entropy == 0.0  # sin diversidad


# ---------------------------------------------------------------------------
# Tests: Lineage Tracker
# ---------------------------------------------------------------------------

class TestLineageTracker:
    def test_register_ingest(self):
        lt = LineageTracker()
        node = lt.register_ingest("doc1", "texto", source="src")
        assert node.stage == "ingest"
        assert node.entity_id == "doc1"
        assert len(node.hash) == 64
        assert node.parent_hash == ""

    def test_full_pipeline_lineage(self):
        lt = LineageTracker()
        n1 = lt.register_ingest("doc1", "texto")
        n2 = lt.register_clean("doc1", "limpio", n1.hash)
        n3 = lt.register_chunk("chunk1", "doc1", "chunk", n2.hash)
        n4 = lt.register_embedding("chunk1", [0.1, 0.2], n3.hash)
        n5 = lt.register_index("chunk1", "idx1", n4.hash)
        n6 = lt.register_retrieval("query", ["chunk1"], [n5.hash])
        n7 = lt.register_generation("response", n6.hash, prompt_version="v1")
        assert len(lt.graph.nodes) == 7
        assert len(lt.graph.edges) == 6

    def test_trace_back(self):
        lt = LineageTracker()
        n1 = lt.register_ingest("doc1", "texto")
        n2 = lt.register_clean("doc1", "limpio", n1.hash)
        n3 = lt.register_chunk("chunk1", "doc1", "chunk", n2.hash)
        chain = lt.trace_back(n3.hash)
        assert len(chain) == 3
        assert chain[0].stage == "chunk"
        assert chain[-1].stage == "ingest"

    def test_lineage_graph_to_dict(self):
        lt = LineageTracker()
        lt.register_ingest("doc1", "texto")
        d = lt.get_full_lineage()
        assert "nodes" in d
        assert "edges" in d
        assert d["node_count"] == 1

    def test_reset(self):
        lt = LineageTracker()
        lt.register_ingest("doc1", "texto")
        lt.reset()
        assert len(lt.graph.nodes) == 0

    def test_hash_inheritance(self):
        lt = LineageTracker()
        n1 = lt.register_ingest("doc1", "texto")
        n2 = lt.register_clean("doc1", "limpio", n1.hash)
        assert n2.parent_hash == n1.hash
        assert n2.hash != n1.hash


# ---------------------------------------------------------------------------
# Tests: Hallucination Detector
# ---------------------------------------------------------------------------

class TestHallucinationDetector:
    def test_clean_response(self):
        hd = HallucinationDetector()
        chunks = ["La política permite cancelar en 30 días.", "Reembolso en 5 días."]
        response = "La política permite cancelar en 30 días y el reembolso toma 5 días."
        report = hd.detect(response, chunks)
        assert not report.is_hallucination
        assert report.coverage_score > 0.5

    def test_hallucination_response(self):
        hd = HallucinationDetector()
        chunks = ["La política permite cancelar en 30 días."]
        response = "El reembolso es inmediato con bonus del 200% sin límite."
        report = hd.detect(response, chunks)
        assert report.is_hallucination or report.severity != "none"
        assert len(report.unsupported_claims) > 0

    def test_empty_response(self):
        hd = HallucinationDetector()
        report = hd.detect("", ["chunk"])
        assert report.is_hallucination
        assert report.severity == "high"

    def test_no_chunks(self):
        hd = HallucinationDetector()
        report = hd.detect("respuesta", [])
        assert report.is_hallucination
        assert report.coverage_score == 0.0

    def test_coverage_score(self):
        hd = HallucinationDetector()
        chunks = ["cancelar 30 días reembolso 5 días"]
        response = "cancelar 30 días reembolso 5 días"
        report = hd.detect(response, chunks)
        assert report.coverage_score == 1.0

    def test_flagged_chunks(self):
        hd = HallucinationDetector()
        chunks = ["texto sobre pagos", "texto completamente diferente sobre vuelos"]
        response = "pagos"
        report = hd.detect(response, chunks)
        # chunk sobre vuelos no contribuye → flagged
        assert len(report.flagged_chunks) >= 1

    def test_severity_levels(self):
        hd = HallucinationDetector()
        # Critical: sin chunks
        r1 = hd.detect("respuesta larga aquí", [])
        assert r1.severity in ("high", "critical")


# ---------------------------------------------------------------------------
# Tests: Prompt Versioning
# ---------------------------------------------------------------------------

class TestPromptRegistry:
    def test_register_prompt(self):
        pr = PromptRegistry()
        p = pr.register("template", version="v1.0", tags=["rag"])
        assert p.id is not None
        assert p.version == "v1.0"
        assert not p.approved

    def test_approve_prompt(self):
        pr = PromptRegistry()
        p = pr.register("template", version="v1.0")
        approved = pr.approve(p.id, approved_by="compliance")
        assert approved.approved
        assert approved.approved_by == "compliance"

    def test_approve_nonexistent(self):
        pr = PromptRegistry()
        result = pr.approve("nonexistent-id")
        assert result is None

    def test_evaluate_prompt(self):
        pr = PromptRegistry()
        p = pr.register("template")
        evaluated = pr.evaluate(p.id, 0.85)
        assert evaluated.evaluation_score == 0.85

    def test_evaluate_clamps_score(self):
        pr = PromptRegistry()
        p = pr.register("template")
        evaluated = pr.evaluate(p.id, 1.5)
        assert evaluated.evaluation_score == 1.0
        evaluated = pr.evaluate(p.id, -0.5)
        assert evaluated.evaluation_score == 0.0

    def test_get_approved(self):
        pr = PromptRegistry()
        p1 = pr.register("t1", version="v1")
        p2 = pr.register("t2", version="v2")
        pr.approve(p1.id)
        approved = pr.get_approved()
        assert len(approved) == 1
        assert approved[0].id == p1.id

    def test_get_latest_approved(self):
        pr = PromptRegistry()
        p1 = pr.register("t1", version="v1")
        pr.approve(p1.id)
        import time
        time.sleep(0.01)
        p2 = pr.register("t2", version="v2")
        pr.approve(p2.id)
        latest = pr.get_latest_approved()
        assert latest.id == p2.id

    def test_get_by_version(self):
        pr = PromptRegistry()
        p = pr.register("template", version="v3.1")
        found = pr.get_by_version("v3.1")
        assert found is not None
        assert found.id == p.id

    def test_history(self):
        pr = PromptRegistry()
        p = pr.register("t", version="v1")
        pr.approve(p.id)
        history = pr.get_history()
        assert len(history) == 2
        assert history[0]["action"] == "registered"
        assert history[1]["action"] == "approved"


# ---------------------------------------------------------------------------
# Tests: Conceptual Drift Detector
# ---------------------------------------------------------------------------

class TestConceptualDriftDetector:
    def test_no_drift(self):
        dd = ConceptualDriftDetector()
        dd.set_baseline("spread", ["bid_ask", "bid_ask", "bid_ask", "credit"])
        report = dd.detect("spread", ["bid_ask", "bid_ask", "bid_ask", "credit"])
        assert not report.is_drift
        assert report.drift_type == "none"

    def test_with_drift(self):
        dd = ConceptualDriftDetector()
        dd.set_baseline("spread", ["bid_ask", "bid_ask", "bid_ask", "bid_ask"])
        report = dd.detect("spread", ["volatilidad", "volatilidad", "volatilidad", "volatilidad"])
        assert report.is_drift
        assert report.drift_type != "none"

    def test_no_baseline(self):
        dd = ConceptualDriftDetector()
        report = dd.detect("unknown_concept", ["a", "b"])
        assert not report.is_drift
        assert "error" in report.details

    def test_drift_score_range(self):
        dd = ConceptualDriftDetector()
        dd.set_baseline("c", ["a", "a", "a", "b"])
        report = dd.detect("c", ["a", "a", "a", "b"])
        assert 0.0 <= report.drift_score <= 1.0

    def test_js_distance_identical(self):
        dd = ConceptualDriftDetector()
        dist = {"a": 0.5, "b": 0.5}
        d = dd._js_distance(dist, dist)
        assert d == 0.0

    def test_js_distance_different(self):
        dd = ConceptualDriftDetector()
        d = dd._js_distance({"a": 1.0}, {"b": 1.0})
        assert d > 0.9

    def test_co_occurrence_drift(self):
        dd = ConceptualDriftDetector()
        dd.set_baseline(
            "concept",
            contexts=["ctx1", "ctx1"],
            co_occurrences=[["term1", "term2"], ["term1"]],
        )
        report = dd.detect(
            "concept",
            current_contexts=["ctx1", "ctx1"],
            current_co_occurrences=[["term3", "term4"]],
        )
        # co-occurrence distribution changed
        assert report.details["co_occurrence_drift"] > 0


# ---------------------------------------------------------------------------
# Tests: Observability
# ---------------------------------------------------------------------------

class TestObservabilityManager:
    def test_log(self):
        om = ObservabilityManager()
        om.log("INFO", "test", trace_id="t1")
        assert len(om.logs) == 1
        assert om.logs[0]["level"] == "INFO"

    def test_increment(self):
        om = ObservabilityManager()
        om.increment("test_total")
        om.increment("test_total")
        assert om.metrics["test_total"] == 2.0

    def test_gauge(self):
        om = ObservabilityManager()
        om.gauge("test_gauge", 42.0)
        assert om.metrics["test_gauge"] == 42.0

    def test_spans(self):
        om = ObservabilityManager()
        span = om.start_span("op", "t1")
        om.end_span(span)
        assert span["end"] is not None
        assert span["duration_ms"] >= 0

    def test_export_prometheus(self):
        om = ObservabilityManager()
        om.increment("test_counter_total")
        om.gauge("test_gauge", 1.5)
        prom = om.export_prometheus()
        assert "test_counter_total" in prom
        assert "test_gauge" in prom
        assert "# TYPE test_counter_total counter" in prom
        assert "# TYPE test_gauge gauge" in prom
        assert 'component="uc162_llmops"' in prom

    def test_summary(self):
        om = ObservabilityManager()
        om.log("INFO", "test")
        om.increment("m_total")
        summary = om.get_summary()
        assert summary["log_count"] == 1
        assert summary["metric_count"] == 1

    def test_reset(self):
        om = ObservabilityManager()
        om.log("INFO", "test")
        om.increment("m")
        om.reset()
        assert len(om.logs) == 0
        assert len(om.metrics) == 0

    def test_to_json(self):
        om = ObservabilityManager()
        om.log("INFO", "test")
        j = om.to_json()
        parsed = json.loads(j)
        assert "logs" in parsed
        assert "metrics" in parsed


# ---------------------------------------------------------------------------
# Tests: LLMOps Guardian (orquestador)
# ---------------------------------------------------------------------------

class TestLLMOpsGuardian:
    def test_process_corpus_balanced(self):
        g = LLMOpsGuardian()
        docs = _balanced_corpus(30)
        result = g.process_corpus(docs, source="trusted")
        assert result.decision == "approve"
        assert result.bias_report["all_passed"]
        assert result.lineage_graph["node_count"] == 30

    def test_process_corpus_biased(self):
        g = LLMOpsGuardian()
        docs = _biased_corpus(20)
        result = g.process_corpus(docs, source="unknown")
        assert result.decision in ("reject", "flag")
        assert not result.bias_report["all_passed"]

    def test_evaluate_response_clean(self):
        g = LLMOpsGuardian()
        result = g.evaluate_response(
            response="La política permite cancelar en 30 días.",
            retrieved_chunks=["La política permite cancelar en 30 días."],
        )
        assert result.decision == "approve"

    def test_evaluate_response_hallucination(self):
        g = LLMOpsGuardian()
        result = g.evaluate_response(
            response="El reembolso es inmediato con bonus del 200%.",
            retrieved_chunks=["La política permite cancelar en 30 días."],
        )
        assert result.decision in ("flag", "reject")

    def test_check_drift_no_drift(self):
        g = LLMOpsGuardian()
        g.set_baseline("spread", ["bid_ask", "bid_ask", "credit"])
        result = g.check_drift("spread", ["bid_ask", "bid_ask", "credit"])
        assert result.decision == "approve"

    def test_check_drift_with_drift(self):
        g = LLMOpsGuardian()
        g.set_baseline("spread", ["bid_ask", "bid_ask", "bid_ask", "bid_ask"])
        result = g.check_drift("spread", ["volatilidad", "volatilidad", "volatilidad", "volatilidad"])
        assert result.decision == "escalate"

    def test_register_and_approve_prompt(self):
        g = LLMOpsGuardian()
        p = g.register_prompt("template", version="v1", tags=["rag"])
        assert p["version"] == "v1"
        approved = g.approve_prompt(p["id"], approved_by="compliance")
        assert approved["approved"]

    def test_get_status(self):
        g = LLMOpsGuardian()
        docs = _balanced_corpus(10)
        g.process_corpus(docs)
        status = g.get_status()
        assert "config" in status
        assert "schema" in status
        assert status["lineage_nodes"] == 10

    def test_get_metrics(self):
        g = LLMOpsGuardian()
        g.process_corpus(_balanced_corpus(30))
        metrics = g.get_metrics()
        assert "llmops_guardian_duration_ms" in metrics
        assert "component=" in metrics

    def test_reset(self):
        g = LLMOpsGuardian()
        g.process_corpus(_balanced_corpus(30))
        g.reset()
        status = g.get_status()
        assert status["lineage_nodes"] == 0

    def test_trace_id_present(self):
        g = LLMOpsGuardian()
        result = g.process_corpus(_balanced_corpus(30))
        assert result.trace_id is not None
        assert len(result.trace_id) > 0

    def test_duration_ms_positive(self):
        g = LLMOpsGuardian()
        result = g.process_corpus(_balanced_corpus(30))
        assert result.duration_ms >= 0


# ---------------------------------------------------------------------------
# Tests: API REST
# ---------------------------------------------------------------------------

class TestAPI:
    @pytest.fixture
    def client(self):
        from api_162 import app, _guardian
        _guardian.reset()
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"

    def test_index(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "endpoints" in data

    def test_schema(self, client):
        resp = client.get("/api/v1/schema")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "input_cards" in data
        assert "output_cards" in data
        assert "POST /api/v1/process-corpus" in data["input_cards"]

    def test_process_corpus_balanced(self, client):
        genders = ["masculino", "femenino", "no_binario"]
        regions = ["latam", "europa", "norteamerica", "asia"]
        perspectives = ["tecnica", "legal", "etica", "economica", "social"]
        source_types = ["academica", "gubernamental", "corporativa", "crowd"]
        periods = ["2023", "2024", "2025"]
        languages = ["es", "en", "es", "en"]
        docs = []
        for i in range(30):
            docs.append({
                "id": f"d{i:03d}",
                "text": f"doc {i}",
                "metadata": {
                    "id_documento": f"d{i:03d}",
                    "fuente": f"src_{i % 5}",
                    "fuente_tipo": source_types[i % len(source_types)],
                    "fecha_creacion": "2025-01-01",
                    "categoria_tema": "trading",
                    "genero_autor": genders[i % len(genders)],
                    "region_geografica": regions[i % len(regions)],
                    "perspectiva_tematica": perspectives[i % len(perspectives)],
                    "idioma": languages[i % len(languages)],
                    "periodo_temporal": periods[i % len(periods)],
                },
            })
        resp = client.post("/api/v1/process-corpus", json={
            "documents": docs,
            "source": "trusted",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["decision"] == "approve"

    def test_process_corpus_biased(self, client):
        docs = []
        for i in range(20):
            docs.append({
                "id": f"d{i:03d}",
                "text": f"doc {i}",
                "metadata": {
                    "id_documento": f"d{i:03d}",
                    "fuente": "single",
                    "fuente_tipo": "corporativa",
                    "fecha_creacion": "2025-01-01",
                    "categoria_tema": "trading",
                    "genero_autor": "masculino",
                    "region_geografica": "norteamerica",
                    "perspectiva_tematica": "tecnica",
                    "idioma": "en",
                    "periodo_temporal": "2025",
                },
            })
        resp = client.post("/api/v1/process-corpus", json={
            "documents": docs,
            "source": "unknown",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["decision"] in ("reject", "flag")

    def test_evaluate_response(self, client):
        resp = client.post("/api/v1/evaluate-response", json={
            "response": "La política permite cancelar en 30 días.",
            "retrieved_chunks": ["La política permite cancelar en 30 días."],
            "prompt_version": "v1",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["decision"] == "approve"

    def test_check_drift(self, client):
        client.post("/api/v1/set-baseline", json={
            "concept_name": "spread",
            "contexts": ["bid_ask", "bid_ask", "credit"],
        })
        resp = client.post("/api/v1/check-drift", json={
            "concept_name": "spread",
            "current_contexts": ["bid_ask", "bid_ask", "credit"],
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["decision"] == "approve"

    def test_register_and_approve_prompt(self, client):
        resp = client.post("/api/v1/register-prompt", json={
            "template": "test template",
            "version": "v1.0",
            "tags": ["rag"],
        })
        assert resp.status_code == 200
        prompt_id = resp.get_json()["id"]
        resp2 = client.post("/api/v1/approve-prompt", json={
            "prompt_id": prompt_id,
            "approved_by": "compliance",
        })
        assert resp2.status_code == 200
        assert resp2.get_json()["approved"]

    def test_approve_nonexistent_prompt(self, client):
        resp = client.post("/api/v1/approve-prompt", json={
            "prompt_id": "nonexistent",
        })
        assert resp.status_code == 404

    def test_status(self, client):
        resp = client.get("/api/v1/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "config" in data
        assert "schema" in data

    def test_prompts_list(self, client):
        client.post("/api/v1/register-prompt", json={
            "template": "t1",
            "version": "v1",
        })
        resp = client.get("/api/v1/prompts")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["prompts"]) == 1

    def test_lineage(self, client):
        docs = [{
            "id": "d1",
            "text": "doc",
            "metadata": {
                "id_documento": "d1",
                "fuente": "s1",
                "fuente_tipo": "academica",
                "fecha_creacion": "2025-01-01",
                "categoria_tema": "trading",
                "genero_autor": "masculino",
                "region_geografica": "latam",
                "perspectiva_tematica": "tecnica",
                "idioma": "es",
                "periodo_temporal": "2025",
            },
        }]
        client.post("/api/v1/process-corpus", json={"documents": docs})
        resp = client.get("/api/v1/lineage")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["node_count"] >= 1

    def test_metrics(self, client):
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert "llmops_" in resp.get_data(as_text=True)

    def test_reset(self, client):
        resp = client.post("/api/v1/reset", json={})
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Tests: Integración end-to-end
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_full_pipeline_balanced(self):
        """Pipeline completo: corpus balanceado → approve → UC-315 recibe."""
        g = LLMOpsGuardian()
        docs = _balanced_corpus(30)
        result = g.process_corpus(docs, source="trusted")
        assert result.decision == "approve"
        # Simular respuesta del LLM con chunks sustantivos
        chunks = ["La política permite cancelar en 30 días.", "El reembolso toma 5 días."]
        response = "La política permite cancelar en 30 días y el reembolso toma 5 días."
        eval_result = g.evaluate_response(response, chunks, prompt_version="v1")
        assert eval_result.decision in ("approve", "flag")

    def test_full_pipeline_biased_then_hallucination(self):
        """Pipeline completo: corpus sesgado → reject → hallucination detectada."""
        g = LLMOpsGuardian()
        docs = _biased_corpus(20)
        result = g.process_corpus(docs, source="unknown")
        assert result.decision in ("reject", "flag")
        # Simular respuesta hallucinada
        response = "El sistema garantiza 100% retorno sin riesgo alguno."
        eval_result = g.evaluate_response(response, ["doc sobre trading"])
        assert eval_result.decision in ("flag", "reject")

    def test_drift_then_rebaseline(self):
        """Drift detectado → re-baseline → no drift."""
        g = LLMOpsGuardian()
        g.set_baseline("concept", ["ctx_a", "ctx_a", "ctx_a"])
        r1 = g.check_drift("concept", ["ctx_b", "ctx_b", "ctx_b"])
        assert r1.decision == "escalate"
        # Re-baseline con nuevo contexto
        g.set_baseline("concept", ["ctx_b", "ctx_b", "ctx_b"])
        r2 = g.check_drift("concept", ["ctx_b", "ctx_b", "ctx_b"])
        assert r2.decision == "approve"

    def test_prompt_lifecycle(self):
        """Ciclo completo de prompt: register → evaluate → approve."""
        g = LLMOpsGuardian()
        p = g.register_prompt("template v1", version="v1.0", tags=["rag"])
        assert not p["approved"]
        g.evaluate_prompt(p["id"], 0.85)
        approved = g.approve_prompt(p["id"], approved_by="compliance")
        assert approved["approved"]
        assert approved["approved_by"] == "compliance"

    def test_lineage_full_traceability(self):
        """Linaje completo: ingesta → generación con trazabilidad."""
        g = LLMOpsGuardian()
        docs = _balanced_corpus(5)
        g.process_corpus(docs, source="trusted")
        # Evaluar respuesta genera nodo de lineage
        g.evaluate_response(
            "respuesta basada en docs",
            [d.text for d in docs[:2]],
            prompt_version="v1",
        )
        status = g.get_status()
        assert status["lineage_nodes"] >= 5  # al menos los de ingesta
