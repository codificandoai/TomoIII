"""
UC-329 — Tests unitarios e integración para GraphRAG-GoT.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from graph_models import (
    GraphNode, GraphEdge, ThoughtNode, ThoughtEdge, ReasoningPath,
    GraphMetrics, GraphRAGGoTResult, GraphRAGGoTConfig,
    NodeType, EdgeType, ReasoningType, ThoughtRole,
)
from knowledge_graph import KnowledgeGraph
from entity_extractor import EntityExtractor
from relation_extractor import RelationExtractor
from graph_rag_retriever import GraphRAGRetriever
from path_ranker import PathRanker
from graph_of_thoughts import GraphOfThoughts
from contradiction_detector import ContradictionDetector
from graph_plasticity import GraphPlasticity
from meta_reasoning import MetaReasoning
from graph_memory import GraphMemory
from observability_329 import ObservabilityManager
from orchestrator_329 import GraphRAGGoTEngine


# ═══════════════════════════════════════════════════════════════════════════
# MODELOS
# ═══════════════════════════════════════════════════════════════════════════

class TestModels:
    def test_graph_node(self):
        n = GraphNode(label="A")
        assert n.node_id != ""
        assert n.to_dict()["label"] == "A"

    def test_graph_edge(self):
        e = GraphEdge(source="a", target="b", edge_type=EdgeType.CAUSES)
        assert e.composite_weight > 0

    def test_reasoning_path(self):
        p = ReasoningPath(nodes=["a", "b"], edges=["e1"])
        assert p.to_dict()["length"] == 2

    def test_graph_rag_got_result(self):
        r = GraphRAGGoTResult(query="q")
        assert r.trace_id != ""


# ═══════════════════════════════════════════════════════════════════════════
# EXTRACTORES
# ═══════════════════════════════════════════════════════════════════════════

class TestEntityExtractor:
    def test_extract_entities(self):
        ex = EntityExtractor(domain_vocabulary=["subsidio", "panel solar"])
        text = "Subsidio del 30% a paneles solares ayuda a China y TSMC."
        entities = ex.extract(text)
        assert len(entities) > 0

    def test_statistics(self):
        ex = EntityExtractor(domain_vocabulary=["x"])
        assert ex.get_statistics()["domain_vocabulary_size"] == 1


class TestRelationExtractor:
    def test_extract_relations(self):
        ex = EntityExtractor(domain_vocabulary=["subsidio"])
        relex = RelationExtractor()
        text = "Subsidio del 30% reduce costos para clientes."
        entities = ex.extract(text)
        relations = relex.extract_relations(text, entities)
        assert isinstance(relations, list)


# ═══════════════════════════════════════════════════════════════════════════
# KNOWLEDGE GRAPH
# ═══════════════════════════════════════════════════════════════════════════

class TestKnowledgeGraph:
    def test_add_nodes_and_edges(self):
        g = KnowledgeGraph()
        n1 = g.add_node(GraphNode(label="A"))
        n2 = g.add_node(GraphNode(label="B"))
        g.add_edge(GraphEdge(source=n1.node_id, target=n2.node_id))
        assert len(g) == 2

    def test_find_paths(self):
        g = KnowledgeGraph()
        a = g.add_node(GraphNode(label="A"))
        b = g.add_node(GraphNode(label="B"))
        c = g.add_node(GraphNode(label="C"))
        g.add_edge(GraphEdge(source=a.node_id, target=b.node_id))
        g.add_edge(GraphEdge(source=b.node_id, target=c.node_id))
        paths = g.find_paths(a.node_id, c.node_id)
        assert len(paths) >= 1

    def test_compute_metrics(self):
        g = KnowledgeGraph()
        g.add_node(GraphNode(label="A"))
        g.add_node(GraphNode(label="B"))
        m = g.compute_metrics()
        assert m.node_count == 2


# ═══════════════════════════════════════════════════════════════════════════
# GRAPHRAG RETRIEVER
# ═══════════════════════════════════════════════════════════════════════════

class TestGraphRAGRetriever:
    def test_retrieve(self):
        retriever = GraphRAGRetriever()
        g = KnowledgeGraph()
        g.add_node(GraphNode(label="renewable energy"))
        g.add_node(GraphNode(label="solar panels"))
        subgraph, scores = retriever.retrieve(g, "solar energy")
        assert subgraph is not None

    def test_embed_query(self):
        retriever = GraphRAGRetriever()
        vec = retriever.embed_query("solar energy")
        assert isinstance(vec, dict)


# ═══════════════════════════════════════════════════════════════════════════
# PATH RANKER
# ═══════════════════════════════════════════════════════════════════════════

class TestPathRanker:
    def test_generate_paths(self):
        g = KnowledgeGraph()
        a = g.add_node(GraphNode(label="A"))
        b = g.add_node(GraphNode(label="B"))
        c = g.add_node(GraphNode(label="C"))
        g.add_edge(GraphEdge(source=a.node_id, target=b.node_id))
        g.add_edge(GraphEdge(source=b.node_id, target=c.node_id))
        ranker = PathRanker(top_k=5)
        paths = ranker.generate_paths(g, [a.node_id], [c.node_id], max_depth=3)
        assert len(paths) >= 1

    def test_diverse_paths(self):
        g = KnowledgeGraph()
        a = g.add_node(GraphNode(label="A"))
        b = g.add_node(GraphNode(label="B"))
        c = g.add_node(GraphNode(label="C"))
        d = g.add_node(GraphNode(label="D"))
        g.add_edge(GraphEdge(source=a.node_id, target=b.node_id))
        g.add_edge(GraphEdge(source=b.node_id, target=c.node_id))
        g.add_edge(GraphEdge(source=a.node_id, target=d.node_id))
        g.add_edge(GraphEdge(source=d.node_id, target=c.node_id))
        ranker = PathRanker(top_k=5)
        paths = ranker.generate_paths(g, [a.node_id], [c.node_id], max_depth=3)
        selected = ranker.select_diverse_paths(paths, k=2)
        assert len(selected) <= 2


# ═══════════════════════════════════════════════════════════════════════════
# GRAPH OF THOUGHTS
# ═══════════════════════════════════════════════════════════════════════════

class TestGraphOfThoughts:
    def test_build_from_paths(self):
        g = KnowledgeGraph()
        a = g.add_node(GraphNode(label="A"))
        b = g.add_node(GraphNode(label="B"))
        c = g.add_node(GraphNode(label="C"))
        e1 = g.add_edge(GraphEdge(source=a.node_id, target=b.node_id))
        e2 = g.add_edge(GraphEdge(source=b.node_id, target=c.node_id))
        path = ReasoningPath(nodes=[a.node_id, b.node_id, c.node_id], edges=[e1.edge_id, e2.edge_id])
        got = GraphOfThoughts()
        got.build_from_paths([path], g)
        assert len(got._thoughts) == 3

    def test_metrics(self):
        got = GraphOfThoughts()
        m = got.compute_metrics()
        assert m.node_count == 0


# ═══════════════════════════════════════════════════════════════════════════
# CONTRADICTION DETECTOR
# ═══════════════════════════════════════════════════════════════════════════

class TestContradictionDetector:
    def test_direct_contradiction(self):
        cd = ContradictionDetector()
        t1 = ThoughtNode(label="A")
        t2 = ThoughtNode(label="B")
        e1 = ThoughtEdge(source=t1.thought_id, target=t2.thought_id, edge_type=EdgeType.SUPPORTS)
        e2 = ThoughtEdge(source=t1.thought_id, target=t2.thought_id, edge_type=EdgeType.REFUTES)
        contradictions = cd.detect({t1.thought_id: t1, t2.thought_id: t2}, {e1.thought_edge_id: e1, e2.thought_edge_id: e2})
        assert len(contradictions) > 0


# ═══════════════════════════════════════════════════════════════════════════
# GRAPH PLASTICITY
# ═══════════════════════════════════════════════════════════════════════════

class TestGraphPlasticity:
    def test_reinforce(self):
        gp = GraphPlasticity()
        g = KnowledgeGraph()
        n1 = g.add_node(GraphNode(label="A"))
        n2 = g.add_node(GraphNode(label="B"))
        e = g.add_edge(GraphEdge(source=n1.node_id, target=n2.node_id, weight=1.0))
        initial = e.weight
        gp.reinforce(g, [n1.node_id, n2.node_id], [e.edge_id], feedback_score=1.0)
        assert e.weight > initial

    def test_penalize(self):
        gp = GraphPlasticity()
        g = KnowledgeGraph()
        n1 = g.add_node(GraphNode(label="A"))
        n2 = g.add_node(GraphNode(label="B"))
        e = g.add_edge(GraphEdge(source=n1.node_id, target=n2.node_id, weight=1.0))
        initial = e.weight
        gp.penalize(g, [n1.node_id, n2.node_id], [e.edge_id], feedback_score=1.0)
        assert e.weight < initial


# ═══════════════════════════════════════════════════════════════════════════
# META REASONING
# ═══════════════════════════════════════════════════════════════════════════

class TestMetaReasoning:
    def test_report(self):
        mr = MetaReasoning()
        report = mr.generate_report("q", [], {}, {}, None)
        assert "recommendations" in report


# ═══════════════════════════════════════════════════════════════════════════
# GRAPH MEMORY
# ═══════════════════════════════════════════════════════════════════════════

class TestGraphMemory:
    def test_save_load_graph(self):
        gm = GraphMemory()
        g = KnowledgeGraph()
        g.add_node(GraphNode(label="A"))
        gm.save_graph(g, key="test", domain="energy")
        loaded = gm.load_graph("test", domain="energy")
        assert loaded is not None

    def test_save_session(self):
        gm = GraphMemory()
        result = GraphRAGGoTResult(query="test")
        sid = gm.save_session(result, domain="energy")
        assert sid is not None


# ═══════════════════════════════════════════════════════════════════════════
# ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════

class TestOrchestrator:
    def test_ingest(self):
        engine = GraphRAGGoTEngine()
        result = engine.ingest("La Union Europea financia paneles solares.", source_id="doc1", domain="energy")
        assert result["entities_added"] >= 1

    def test_reason(self):
        engine = GraphRAGGoTEngine()
        engine.ingest("Subsidio del 30% reduce costos de paneles solares.", source_id="doc1", domain="energy")
        engine.ingest("Competidor chino reduce precios 10% anual.", source_id="doc2", domain="energy")
        result = engine.reason("¿Cómo afectan subsidios a rentabilidad solar?", domain="energy")
        assert result.trace_id != ""
        assert result.duration_ms >= 0

    def test_feedback(self):
        engine = GraphRAGGoTEngine()
        engine.ingest("Subsidio del 30% reduce costos.", source_id="doc1", domain="energy")
        result = engine.reason("test", domain="energy")
        fb = engine.feedback(result.trace_id, "success", 1.0)
        assert "status" in fb


# ═══════════════════════════════════════════════════════════════════════════
# API FLASK
# ═══════════════════════════════════════════════════════════════════════════

class TestAPI:
    @pytest.fixture
    def client(self):
        from api_329 import app
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

    def test_ingest(self, client):
        resp = client.post("/api/v1/graphrag-got/ingest", json={
            "text": "Subsidio del 30% reduce costos de paneles solares.",
            "source_id": "doc1",
            "domain": "energy",
        })
        assert resp.status_code == 200

    def test_reason(self, client):
        client.post("/api/v1/graphrag-got/ingest", json={
            "text": "Subsidio del 30% reduce costos de paneles solares.",
            "source_id": "doc1",
            "domain": "energy",
        })
        resp = client.post("/api/v1/graphrag-got/reason", json={
            "query": "¿Cómo afectan subsidios a rentabilidad solar?",
            "domain": "energy",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "trace_id" in data

    def test_feedback(self, client):
        r1 = client.post("/api/v1/graphrag-got/reason", json={"query": "test", "domain": "x"})
        trace_id = r1.get_json()["trace_id"]
        resp = client.post("/api/v1/graphrag-got/feedback", json={
            "trace_id": trace_id,
            "outcome": "success",
        })
        assert resp.status_code == 200

    def test_stats(self, client):
        resp = client.get("/api/v1/graphrag-got/stats")
        assert resp.status_code == 200
