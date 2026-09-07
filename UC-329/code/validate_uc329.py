"""
UC-329 — Validación operacional de GraphRAG-GoT.

Verifica los 12 procesos principales:
1. Modelos de datos y configuración.
2. Extractor de entidades.
3. Extractor de relaciones.
4. Knowledge Graph.
5. GraphRAG retriever.
6. Path ranker.
7. Graph of Thoughts.
8. Contradiction detector.
9. Graph plasticity.
10. Meta reasoning.
11. Graph memory.
12. Motor GraphRAG-GoT completo.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))


def validate_models():
    from graph_models import (
        GraphNode, GraphEdge, ThoughtNode, ThoughtEdge, ReasoningPath,
        GraphMetrics, GraphRAGGoTResult, GraphRAGGoTConfig,
    )
    n = GraphNode(label="test")
    e = GraphEdge(source=n.node_id, target=n.node_id)
    t = ThoughtNode(label="test")
    p = ReasoningPath(nodes=[n.node_id], edges=[e.edge_id])
    m = GraphMetrics(node_count=2, edge_count=1)
    cfg = GraphRAGGoTConfig()
    r = GraphRAGGoTResult(query="test")
    assert r.trace_id != ""
    assert cfg.max_search_depth > 0
    return True


def validate_entity_extractor():
    from entity_extractor import EntityExtractor
    ex = EntityExtractor(domain_vocabulary=["subsidio", "panel solar"])
    text = "Subsidio del 30% a paneles solares ayuda a China y TSMC."
    entities = ex.extract(text)
    assert len(entities) > 0
    return True


def validate_relation_extractor():
    from entity_extractor import EntityExtractor
    from relation_extractor import RelationExtractor
    ex = EntityExtractor(domain_vocabulary=["subsidio"])
    relex = RelationExtractor()
    text = "Subsidio del 30% reduce costos para clientes."
    entities = ex.extract(text)
    relations = relex.extract_relations(text, entities)
    assert isinstance(relations, list)
    return True


def validate_knowledge_graph():
    from knowledge_graph import KnowledgeGraph
    from graph_models import GraphNode, GraphEdge
    g = KnowledgeGraph()
    n1 = g.add_node(GraphNode(label="A"))
    n2 = g.add_node(GraphNode(label="B"))
    g.add_edge(GraphEdge(source=n1.node_id, target=n2.node_id))
    assert len(g) == 2
    paths = g.find_paths(n1.node_id, n2.node_id)
    assert len(paths) >= 1
    return True


def validate_graph_rag_retriever():
    from graph_rag_retriever import GraphRAGRetriever
    from knowledge_graph import KnowledgeGraph
    from graph_models import GraphNode
    retriever = GraphRAGRetriever()
    g = KnowledgeGraph()
    n1 = g.add_node(GraphNode(label="renewable energy"))
    n2 = g.add_node(GraphNode(label="solar panels"))
    subgraph, scores = retriever.retrieve(g, "solar energy")
    assert subgraph is not None
    return True


def validate_path_ranker():
    from path_ranker import PathRanker
    from knowledge_graph import KnowledgeGraph
    from graph_models import GraphNode, GraphEdge
    g = KnowledgeGraph()
    a = g.add_node(GraphNode(label="A"))
    b = g.add_node(GraphNode(label="B"))
    c = g.add_node(GraphNode(label="C"))
    g.add_edge(GraphEdge(source=a.node_id, target=b.node_id))
    g.add_edge(GraphEdge(source=b.node_id, target=c.node_id))
    ranker = PathRanker(top_k=5)
    paths = ranker.generate_paths(g, [a.node_id], [c.node_id], max_depth=3)
    assert len(paths) >= 1
    return True


def validate_graph_of_thoughts():
    from graph_of_thoughts import GraphOfThoughts
    from knowledge_graph import KnowledgeGraph
    from graph_models import GraphNode, GraphEdge, ReasoningPath
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
    return True


def validate_contradiction_detector():
    from contradiction_detector import ContradictionDetector
    from graph_models import ThoughtNode, ThoughtEdge, EdgeType
    cd = ContradictionDetector()
    t1 = ThoughtNode(label="A")
    t2 = ThoughtNode(label="B")
    e1 = ThoughtEdge(source=t1.thought_id, target=t2.thought_id, edge_type=EdgeType.SUPPORTS)
    e2 = ThoughtEdge(source=t1.thought_id, target=t2.thought_id, edge_type=EdgeType.REFUTES)
    contradictions = cd.detect({t1.thought_id: t1, t2.thought_id: t2}, {e1.thought_edge_id: e1, e2.thought_edge_id: e2})
    assert len(contradictions) > 0
    return True


def validate_graph_plasticity():
    from graph_plasticity import GraphPlasticity
    from knowledge_graph import KnowledgeGraph
    from graph_models import GraphNode, GraphEdge
    gp = GraphPlasticity()
    g = KnowledgeGraph()
    n1 = g.add_node(GraphNode(label="A"))
    n2 = g.add_node(GraphNode(label="B"))
    e = g.add_edge(GraphEdge(source=n1.node_id, target=n2.node_id, weight=1.0))
    initial = e.weight
    gp.reinforce(g, [n1.node_id, n2.node_id], [e.edge_id], feedback_score=1.0)
    assert e.weight > initial
    return True


def validate_meta_reasoning():
    from meta_reasoning import MetaReasoning
    mr = MetaReasoning()
    mr.record_exploration("test")
    report = mr.generate_report("q", [], {}, [], None)
    assert "recommendations" in report
    return True


def validate_graph_memory():
    from graph_memory import GraphMemory
    from knowledge_graph import KnowledgeGraph
    from graph_models import GraphNode, GraphRAGGoTResult
    gm = GraphMemory()
    g = KnowledgeGraph()
    g.add_node(GraphNode(label="A"))
    key = gm.save_graph(g, key="test", domain="energy")
    loaded = gm.load_graph("test", domain="energy")
    assert loaded is not None
    result = GraphRAGGoTResult(query="test")
    sid = gm.save_session(result, domain="energy")
    assert sid is not None
    return True


def validate_orchestrator():
    from orchestrator_329 import GraphRAGGoTEngine
    engine = GraphRAGGoTEngine()
    engine.ingest("Subsidio del 30% reduce costos de paneles solares.", source_id="doc1", domain="energy")
    engine.ingest("Competidor chino reduce precios 10% anual.", source_id="doc2", domain="energy")
    result = engine.reason("¿Cómo afectan subsidios a rentabilidad solar?", domain="energy")
    assert result is not None
    assert result.trace_id != ""
    return True


def main():
    print("=" * 70)
    print("UC-329 — Validación Operacional GraphRAG-GoT")
    print("=" * 70)

    validations = [
        ("Modelos de datos y configuración", validate_models),
        ("Extractor de entidades", validate_entity_extractor),
        ("Extractor de relaciones", validate_relation_extractor),
        ("Knowledge Graph", validate_knowledge_graph),
        ("GraphRAG retriever", validate_graph_rag_retriever),
        ("Path ranker", validate_path_ranker),
        ("Graph of Thoughts", validate_graph_of_thoughts),
        ("Contradiction detector", validate_contradiction_detector),
        ("Graph plasticity", validate_graph_plasticity),
        ("Meta reasoning", validate_meta_reasoning),
        ("Graph memory", validate_graph_memory),
        ("Motor GraphRAG-GoT completo", validate_orchestrator),
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
        print("  Todos los 12 procesos están funcionando correctamente.")
    else:
        print("  ALGUNOS PROCESOS FALLARON.")
        sys.exit(1)


if __name__ == "__main__":
    main()
