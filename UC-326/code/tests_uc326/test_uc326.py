"""
UC-326 — Tests unitarios e integración para MAQRI.

Cubre:
- Modelos de datos.
- Memoria episódica, semántica, procedimental.
- Refinamiento de queries con memoria.
- Divergencia forzada.
- Critic.
- Cross-retrieval.
- Motor MAQRI completo.
- API Flask.
"""

import sys
import os
import pytest
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from maqri_models import (
    MaqriConfig, MaqriResult, MaqriIteration, SearchEpisode,
    RetrievedDocument, QueryVariant, ProceduralRule, CriticAssessment,
    WorkingMemory, MemoryQuery, MemoryType, QueryStrategy, RetrievalVerdict,
)
from episodic_memory import EpisodicMemory
from semantic_memory import SemanticMemory
from procedural_memory import ProceduralMemory
from divergence_strategy import DivergenceStrategy
from query_refiner_326 import QueryRefiner326
from critic_evaluator import CriticEvaluator
from cross_retriever import CrossRetriever
from maqri_engine import MaqriEngine
from observability_326 import ObservabilityManager

from importlib import import_module
_mod = import_module("UC-326")
UCMaqriLayer = _mod.UCMaqriLayer


# ═══════════════════════════════════════════════════════════════════════════
# MODELOS DE DATOS
# ═══════════════════════════════════════════════════════════════════════════

class TestModels:
    """Tests para maqri_models.py."""

    def test_retrieved_document_fingerprint(self):
        d1 = RetrievedDocument(content="hello world", source="a")
        d2 = RetrievedDocument(content="hello  world", source="b")
        assert d1.fingerprint == d2.fingerprint

    def test_critic_assessment_overall(self):
        a = CriticAssessment(relevance_score=0.8, coverage_score=0.7, novelty_score=0.6)
        assert 0.7 <= a.overall_score <= 0.75

    def test_search_episode_success(self):
        ep = SearchEpisode(original_query="a", refined_query="b", relevance_score=0.9)
        assert ep.success is True
        ep2 = SearchEpisode(original_query="a", refined_query="b", relevance_score=0.9, failure_reason="x")
        assert ep2.success is False

    def test_working_memory(self):
        wm = WorkingMemory(original_goal="test", accumulated_facts=["f1"])
        assert wm.to_dict()["original_goal"] == "test"

    def test_maqri_result_unique_facts(self):
        r = MaqriResult()
        r.working_memory.accumulated_facts = ["a", "a", "b"]
        assert len(r.unique_facts) == 2

    def test_query_variant_to_dict(self):
        v = QueryVariant(query="test", strategy=QueryStrategy.EXPAND, estimated_quality=0.8)
        d = v.to_dict()
        assert d["strategy"] == "expand"
        assert d["estimated_quality"] == 0.8


# ═══════════════════════════════════════════════════════════════════════════
# MEMORIA EPISÓDICA
# ═══════════════════════════════════════════════════════════════════════════

class TestEpisodicMemory:
    """Tests para episodic_memory.py."""

    def test_add_and_len(self):
        m = EpisodicMemory()
        m.add(SearchEpisode(original_query="a", refined_query="b", relevance_score=0.5))
        assert len(m) == 1

    def test_find_similar(self):
        m = EpisodicMemory()
        m.add(SearchEpisode(original_query="pricing strategies", refined_query="dynamic pricing", relevance_score=0.8))
        m.add(SearchEpisode(original_query="machine learning", refined_query="ml models", relevance_score=0.7))
        similar = m.find_similar("pricing strategies", top_k=1, threshold=0.3)
        assert len(similar) == 1

    def test_is_redundant(self):
        m = EpisodicMemory()
        m.add(SearchEpisode(original_query="test query", refined_query="test query", relevance_score=0.5))
        assert m.is_redundant("test query", threshold=0.9) is True
        assert m.is_redundant("different topic", threshold=0.9) is False

    def test_failed_strategies(self):
        m = EpisodicMemory()
        m.add(SearchEpisode(original_query="a", refined_query="b", relevance_score=0.2, failure_reason="too broad"))
        failed = m.get_failed_strategies()
        assert "too broad" in failed

    def test_successful_queries(self):
        m = EpisodicMemory()
        m.add(SearchEpisode(original_query="a", refined_query="b", relevance_score=0.8))
        queries = m.get_successful_queries()
        assert "b" in queries

    def test_get_statistics(self):
        m = EpisodicMemory()
        m.add(SearchEpisode(original_query="a", refined_query="b", relevance_score=0.8))
        stats = m.get_statistics()
        assert stats["total"] == 1
        assert stats["successes"] == 1

    def test_reset(self):
        m = EpisodicMemory()
        m.add(SearchEpisode(original_query="a", refined_query="b", relevance_score=0.5))
        m.reset()
        assert len(m) == 0


# ═══════════════════════════════════════════════════════════════════════════
# MEMORIA SEMÁNTICA
# ═══════════════════════════════════════════════════════════════════════════

class TestSemanticMemory:
    """Tests para semantic_memory.py."""

    def test_add_and_retrieve(self):
        m = SemanticMemory()
        m.add_document("Dynamic pricing based on elasticity", source="pricing")
        results = m.retrieve("pricing strategies")
        assert len(results) >= 1

    def test_add_documents(self):
        m = SemanticMemory()
        docs = [{"content": "a"}, {"content": "b"}]
        added = m.add_documents(docs, source="kb")
        assert len(added) == 2

    def test_source_filter(self):
        m = SemanticMemory()
        m.add_document("Dynamic pricing", source="pricing")
        m.add_document("LSTM model", source="ml")
        results = m.retrieve("pricing", source_filter="pricing")
        assert len(results) == 1

    def test_get_sources(self):
        m = SemanticMemory()
        m.add_document("a", source="x")
        m.add_document("b", source="y")
        assert set(m.get_sources()) == {"x", "y"}

    def test_stats(self):
        m = SemanticMemory()
        m.add_document("a", source="x")
        stats = m.get_stats()
        assert stats["total_documents"] == 1

    def test_reset(self):
        m = SemanticMemory()
        m.add_document("a")
        m.reset()
        assert len(m) == 0


# ═══════════════════════════════════════════════════════════════════════════
# MEMORIA PROCEDIMENTAL
# ═══════════════════════════════════════════════════════════════════════════

class TestProceduralMemory:
    """Tests para procedural_memory.py."""

    def test_default_rules(self):
        m = ProceduralMemory()
        assert len(m.get_rules()) >= 4

    def test_evaluate_low_results(self):
        m = ProceduralMemory()
        active = m.evaluate(num_results=2)
        assert any(r.name == "low_results_expand" for r in active)

    def test_evaluate_low_relevance(self):
        m = ProceduralMemory()
        active = m.evaluate(avg_relevance=0.1)
        assert any(r.name == "low_relevance_diverge" for r in active)

    def test_recommended_strategies(self):
        m = ProceduralMemory()
        strategies = m.get_recommended_strategies(num_results=2)
        assert QueryStrategy.EXPAND in strategies

    def test_update_rule_success(self):
        m = ProceduralMemory()
        rules = m._rules
        rule_id = rules[0].rule_id
        m.update_rule_success(rule_id, True)
        assert rules[0].hits == 1
        assert rules[0].successes == 1


# ═══════════════════════════════════════════════════════════════════════════
# DIVERGENCIA
# ═══════════════════════════════════════════════════════════════════════════

class TestDivergenceStrategy:
    """Tests para divergence_strategy.py."""

    def test_apply_synonyms(self):
        d = DivergenceStrategy()
        result = d.diverge("pricing strategies", [], QueryStrategy.DIVERGE)
        assert result != "pricing strategies"

    def test_expand(self):
        d = DivergenceStrategy()
        result = d.diverge("test", [], QueryStrategy.EXPAND)
        assert "overview" in result or "broader" in result

    def test_specialize(self):
        d = DivergenceStrategy()
        result = d.diverge("pricing", ["too broad"], QueryStrategy.SPECIALIZE)
        assert "specific" in result or "implementation" in result

    def test_generate_variants(self):
        d = DivergenceStrategy()
        variants = d.generate_divergent_variants("pricing api", n=3)
        assert len(variants) > 0
        assert len(set(variants)) == len(variants)


# ═══════════════════════════════════════════════════════════════════════════
# QUERY REFINER
# ═══════════════════════════════════════════════════════════════════════════

class TestQueryRefiner:
    """Tests para query_refiner_326.py."""

    def test_generate_variants(self):
        refiner = QueryRefiner326()
        variants = refiner.generate_variants("MAQRI memory")
        assert len(variants) > 0

    def test_learn_from_episodes(self):
        episodic = EpisodicMemory()
        episodic.add(SearchEpisode(
            original_query="test",
            refined_query="improved test",
            relevance_score=0.9,
        ))
        refiner = QueryRefiner326(episodic=episodic)
        variants = refiner.generate_variants("test")
        assert any(v.query == "improved test" for v in variants)

    def test_refine_from_failure(self):
        refiner = QueryRefiner326()
        v = refiner.refine_from_failure(
            query="pricing",
            missing_info="implementation details",
            failure_reason="too broad",
            accumulated_facts=["Dynamic pricing uses elasticity"],
        )
        assert v.query != ""
        assert "implementation details" in v.query

    def test_is_too_broad(self):
        refiner = QueryRefiner326()
        assert refiner._is_too_broad("what is this about") is True
        assert refiner._is_too_broad("dynamic pricing strategies for SaaS") is False

    def test_is_too_specific(self):
        refiner = QueryRefiner326()
        assert refiner._is_too_specific("a very long query with many technical terms about complex implementation details") is True
        assert refiner._is_too_specific("short query") is False


# ═══════════════════════════════════════════════════════════════════════════
# CRITIC
# ═══════════════════════════════════════════════════════════════════════════

class TestCritic:
    """Tests para critic_evaluator.py."""

    def test_evaluate_relevant_docs(self):
        c = CriticEvaluator()
        docs = [RetrievedDocument(content="Dynamic pricing based on elasticity", source="a")]
        wm = WorkingMemory()
        assessment = c.evaluate("pricing strategies", docs, wm)
        assert assessment.relevance_score > 0

    def test_should_continue_low_confidence(self):
        c = CriticEvaluator()
        a = CriticAssessment(confidence=0.3, failure_reason="too broad")
        assert c.should_continue(a) is True

    def test_should_continue_high_confidence(self):
        c = CriticEvaluator()
        a = CriticAssessment(confidence=0.9)
        assert c.should_continue(a) is False

    def test_evaluate_novelty_with_known_facts(self):
        c = CriticEvaluator()
        docs = [RetrievedDocument(content="known fact", source="a")]
        wm = WorkingMemory(accumulated_facts=["known fact"])
        assessment = c.evaluate("query", docs, wm)
        assert assessment.novelty_score < 1.0


# ═══════════════════════════════════════════════════════════════════════════
# CROSS-RETRIEVER
# ═══════════════════════════════════════════════════════════════════════════

class TestCrossRetriever:
    """Tests para cross_retriever.py."""

    def test_search_semantic(self):
        semantic = SemanticMemory()
        semantic.add_document("pricing strategies for dynamic elasticity", source="pricing")
        cr = CrossRetriever(semantic=semantic)
        docs = cr.search("pricing strategies")
        assert len(docs) >= 1

    def test_external_retriever(self):
        semantic = SemanticMemory()
        semantic.add_document("Dynamic pricing", source="pricing")

        def external(q, top_k):
            return [{"content": f"External: {q}", "source": "api", "score": 0.9}]

        cr = CrossRetriever(semantic=semantic, external_retrievers={"api": external})
        docs = cr.search("pricing")
        assert any(d.memory_type == MemoryType.EXTERNAL for d in docs)

    def test_deduplication(self):
        semantic = SemanticMemory()
        semantic.add_document("same content", source="a")
        semantic.add_document("same content", source="b")
        cr = CrossRetriever(semantic=semantic)
        docs = cr.search("same content")
        assert len(docs) == 1


# ═══════════════════════════════════════════════════════════════════════════
# MOTOR MAQRI
# ═══════════════════════════════════════════════════════════════════════════

class TestMaqriEngine:
    """Tests para maqri_engine.py."""

    def test_basic_search(self):
        semantic = SemanticMemory()
        semantic.add_document("MAQRI improves iterative query refinement", source="maqri")
        engine = MaqriEngine(semantic=semantic)
        result = engine.search("MAQRI query refinement", max_iterations=2)
        assert result.iterations_executed > 0
        assert result.trace_id != ""

    def test_search_returns_docs(self):
        semantic = SemanticMemory()
        semantic.add_document("MAQRI improves iterative query refinement", source="maqri")
        engine = MaqriEngine(semantic=semantic)
        result = engine.search("MAQRI iterative query refinement improves", max_iterations=2)
        assert len(result.docs) > 0

    def test_search_respects_max_iterations(self):
        semantic = SemanticMemory()
        semantic.add_document("topic X", source="kb")
        engine = MaqriEngine(semantic=semantic)
        result = engine.search("unrelated query", max_iterations=1)
        assert result.iterations_executed <= 1

    def test_verdict_type(self):
        semantic = SemanticMemory()
        semantic.add_document("MAQRI", source="maqri")
        engine = MaqriEngine(semantic=semantic)
        result = engine.search("MAQRI", max_iterations=2)
        assert result.verdict in (
            RetrievalVerdict.CONVERGED,
            RetrievalVerdict.MAX_ITERATIONS,
            RetrievalVerdict.INSUFFICIENT_DATA,
        )

    def test_history(self):
        semantic = SemanticMemory()
        semantic.add_document("MAQRI", source="maqri")
        engine = MaqriEngine(semantic=semantic)
        engine.search("MAQRI", max_iterations=1)
        engine.search("query", max_iterations=1)
        assert len(engine.get_history()) == 2

    def test_observability(self):
        semantic = SemanticMemory()
        semantic.add_document("MAQRI", source="maqri")
        engine = MaqriEngine(semantic=semantic)
        engine.search("MAQRI", max_iterations=1)
        summary = engine.get_observability_summary()
        assert summary["total_logs"] > 0

    def test_reset(self):
        semantic = SemanticMemory()
        semantic.add_document("MAQRI", source="maqri")
        engine = MaqriEngine(semantic=semantic)
        engine.search("MAQRI", max_iterations=1)
        engine.reset()
        assert len(engine.get_history()) == 0


# ═══════════════════════════════════════════════════════════════════════════
# UC-326 CAPA
# ═══════════════════════════════════════════════════════════════════════════

class TestUCMaqriLayer:
    """Tests para UC-326.py."""

    def test_layer_search(self):
        layer = UCMaqriLayer()
        result = layer.retrieve_with_context("MAQRI es un motor de refinamiento iterativo", max_iterations=2)
        assert result.iterations_executed > 0

    def test_layer_retrieve_interface(self):
        layer = UCMaqriLayer()
        docs = layer.retrieve("MAQRI memory", top_k=3)
        assert isinstance(docs, list)

    def test_add_documents(self):
        layer = UCMaqriLayer()
        docs = [{"content": "test document", "source": "test"}]
        added = layer.add_documents(docs)
        assert len(added) == 1

    def test_add_experience(self):
        layer = UCMaqriLayer()
        from maqri_models import RetrievedDocument
        episode = layer.add_experience(
            query="q",
            refined_query="rq",
            docs=[RetrievedDocument(content="d", source="s")],
            relevance_score=0.8,
            
        )
        assert episode.original_query == "q"


# ═══════════════════════════════════════════════════════════════════════════
# API FLASK
# ═══════════════════════════════════════════════════════════════════════════

class TestAPI:
    """Tests para api_326.py."""

    @pytest.fixture
    def client(self):
        from api_326 import app
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "ok"

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

    def test_search(self, client):
        resp = client.post("/api/v1/maqri/search", json={
            "query": "MAQRI memory",
            "max_iterations": 1,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "verdict" in data
        assert "iterations_executed" in data

    def test_search_missing_query(self, client):
        resp = client.post("/api/v1/maqri/search", json={})
        assert resp.status_code == 400

    def test_documents(self, client):
        resp = client.post("/api/v1/maqri/documents", json={
            "documents": [{"content": "test doc"}],
            "source": "api",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["indexed"] == 1

    def test_documents_invalid(self, client):
        resp = client.post("/api/v1/maqri/documents", json={"documents": "not list"})
        assert resp.status_code == 400

    def test_critic(self, client):
        resp = client.post("/api/v1/maqri/critic", json={
            "query": "pricing strategies",
            "documents": ["Dynamic pricing based on elasticity"],
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "relevance_score" in data

    def test_refine(self, client):
        resp = client.post("/api/v1/maqri/refine", json={
            "query": "pricing",
            "context": "building RAG",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "variants" in data

    def test_metrics(self, client):
        resp = client.get("/metrics")
        assert resp.status_code == 200
