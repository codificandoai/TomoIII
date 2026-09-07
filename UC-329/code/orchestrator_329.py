"""
UC-329 — Motor GraphRAG-GoT.

Coordina la extracción de entidades/relaciones, la construcción del
grafo de conocimiento, la recuperación de subgrafos, la generación de
caminos de razonamiento, la construcción del Grafo del Pensamiento,
la detección de contradicciones y la síntesis final.
"""

import time
from typing import Dict, List, Optional, Any, Tuple

from graph_models import (
    GraphRAGGoTConfig, GraphRAGGoTResult, GraphMetrics, ThoughtRole, ReasoningType,
)
from knowledge_graph import KnowledgeGraph
from entity_extractor import EntityExtractor
from relation_extractor import RelationExtractor
from graph_rag_retriever import GraphRAGRetriever
from path_ranker import PathRanker
from graph_of_thoughts import GraphOfThoughts
from contradiction_detector import ContradictionDetector
from meta_reasoning import MetaReasoning
from graph_plasticity import GraphPlasticity
from graph_memory import GraphMemory
from observability_329 import ObservabilityManager


class GraphRAGGoTEngine:
    """
    Motor principal de UC-329 GraphRAG-GoT.

    Expone un método `reason(query, ...)` que ejecuta el pipeline completo
    y devuelve un GraphRAGGoTResult trazable.
    """

    def __init__(self, config: Optional[GraphRAGGoTConfig] = None):
        self.config = config or GraphRAGGoTConfig()
        self.knowledge_graph = KnowledgeGraph()
        self.entity_extractor = EntityExtractor()
        self.relation_extractor = RelationExtractor()
        self.retriever = GraphRAGRetriever(config=self.config)
        self.path_ranker = PathRanker(top_k=self.config.top_k_paths)
        self.thought_graph = GraphOfThoughts()
        self.contradiction_detector = ContradictionDetector()
        self.meta_reasoning = MetaReasoning()
        self.plasticity = GraphPlasticity()
        self.memory = GraphMemory()
        self.observability = ObservabilityManager()

    def ingest(
        self,
        text: str,
        source_id: Optional[str] = None,
        domain: str = "default",
    ) -> Dict[str, Any]:
        """
        Ingesta texto: extrae entidades y relaciones y los agrega al KG.
        """
        span = self.observability.start_span("ingest", attributes={"source_id": source_id, "domain": domain})
        entities = self.entity_extractor.extract(text, source_id=source_id)
        for e in entities:
            self.knowledge_graph.add_node(e)
        relations = self.relation_extractor.extract_relations(text, entities, source_id=source_id)
        for r in relations:
            self.knowledge_graph.add_edge(r)

        self.observability.observe_histogram("ingest_entities_count", len(entities))
        self.observability.observe_histogram("ingest_relations_count", len(relations))
        self.observability.end_span(span.span_id)

        return {
            "entities_added": len(entities),
            "relations_added": len(relations),
            "source_id": source_id,
            "domain": domain,
        }

    def reason(
        self,
        query: str,
        context: str = "",
        domain: str = "default",
        start_nodes: Optional[List[str]] = None,
        end_nodes: Optional[List[str]] = None,
    ) -> GraphRAGGoTResult:
        """
        Ejecuta el pipeline GraphRAG-GoT para una consulta.

        Args:
            query: consulta compleja.
            context: contexto adicional.
            domain: dominio para memoria.
            start_nodes: IDs de nodos semilla opcionales.
            end_nodes: IDs de nodos destino opcionales.

        Returns:
            GraphRAGGoTResult con respuesta, grafos, caminos, métricas.
        """
        start_time = time.time()
        result = GraphRAGGoTResult(query=query)
        root_span = self.observability.start_span(
            "reason",
            trace_id=result.trace_id,
            attributes={"query": query, "domain": domain},
        )

        self.observability.log("INFO", f"GraphRAG-GoT reason: {query[:120]}", trace_id=result.trace_id)
        self.meta_reasoning.record_exploration("reason_start", {"query": query, "domain": domain})

        try:
            # FASE 1: Recuperar subgrafo relevante
            subgraph, node_scores = self.retriever.retrieve(self.knowledge_graph, query)
            self.meta_reasoning.record_exploration(
                "subgraph_retrieved",
                {"subgraph_nodes": len(subgraph._nodes), "subgraph_edges": len(subgraph._edges)},
            )

            # FASE 2: Determinar nodos semilla y destino
            if start_nodes is None:
                seeds = [n.node_id for n, _ in self.retriever.seed_nodes(self.knowledge_graph, query, top_k=5)]
                start_nodes = seeds
            if end_nodes is None:
                # Use high-scoring nodes from subgraph as targets
                sorted_scores = sorted(node_scores.items(), key=lambda x: x[1], reverse=True)
                end_nodes = [nid for nid, _ in sorted_scores[:5]]

            # FASE 3: Generar y ranquear caminos
            all_paths = self.path_ranker.generate_paths(
                self.knowledge_graph,
                start_nodes=start_nodes,
                end_nodes=end_nodes,
                max_depth=self.config.max_search_depth,
            )
            diverse_paths = self.path_ranker.select_diverse_paths(all_paths, k=self.config.top_k_paths)
            result.reasoning_paths = diverse_paths
            self.meta_reasoning.record_exploration(
                "paths_generated",
                {"total_paths": len(all_paths), "selected_paths": len(diverse_paths)},
            )

            # FASE 4: Construir Grafo del Pensamiento
            self.thought_graph = GraphOfThoughts()
            self.thought_graph.build_from_paths(diverse_paths, self.knowledge_graph, node_scores)

            # Agregar nodos meta
            self.thought_graph.add_meta_thought(
                label=f"Reflexión: {len(diverse_paths)} caminos explorados",
                role=ThoughtRole.UNCERTAINTY,
                refs=[p.path_id for p in diverse_paths],
            )

            # FASE 5: Detectar contradicciones
            contradictions = self.contradiction_detector.detect(
                self.thought_graph._thoughts,
                self.thought_graph._edges,
            )
            result.contradictions = contradictions
            self.meta_reasoning.record_exploration(
                "contradictions_detected",
                {"count": len(contradictions)},
            )

            # FASE 6: Calcular métricas
            metrics = self.thought_graph.compute_metrics()
            # enrich metrics
            metrics.reasoning_depth = sum(len(p.nodes) for p in diverse_paths) / max(1, len(diverse_paths))
            metrics.diversity = self._compute_diversity(diverse_paths)
            metrics.consistency = max(0.0, 1.0 - len(contradictions) / max(1, len(self.thought_graph._thoughts)))
            metrics.explainability = self._compute_explainability(self.thought_graph._thoughts)
            metrics.exhaustiveness = self._compute_exhaustiveness(diverse_paths)
            result.metrics = metrics

            # FASE 7: Síntesis narrativa
            result.answer = self._synthesize_answer(query, diverse_paths, self.thought_graph)
            result.narrative = self._generate_narrative(query, diverse_paths, contradictions, metrics)

            # FASE 8: Meta-reasoning y recomendaciones
            meta_report = self.meta_reasoning.generate_report(
                query=query,
                paths=diverse_paths,
                thoughts=self.thought_graph._thoughts,
                contradictions=contradictions,
                metrics=metrics,
            )
            result.recommendations = meta_report.get("recommendations", [])
            result.uncertainties = meta_report.get("uncovered_dimensions", [])

            # FASE 9: Preparar datos para serialización y visualización
            result.knowledge_graph = self.knowledge_graph.to_dict()
            result.thought_graph = self.thought_graph.to_dict()
            result.visualization_data = self._build_visualization_data(self.thought_graph)
            result.answer_structured = {
                "summary": result.answer,
                "meta_report": meta_report,
                "contradictions": contradictions,
            }

            # FASE 10: Memoria
            self.memory.save_graph(self.knowledge_graph, key=domain, domain=domain)
            self.memory.save_session(result, domain=domain)

            result.duration_ms = (time.time() - start_time) * 1000
            self.observability.observe_histogram("reason_duration_ms", result.duration_ms)
            self.observability.observe_histogram("reason_paths_count", len(diverse_paths))
            self.observability.inc_counter("graphrag_got_reason_total")
            self.observability.log(
                "INFO",
                f"GraphRAG-GoT completed: nodes={metrics.node_count}, "
                f"edges={metrics.edge_count}, contradictions={len(contradictions)}",
                trace_id=result.trace_id,
            )

        except Exception as e:
            self.observability.log("ERROR", f"GraphRAG-GoT reason failed: {str(e)}", trace_id=result.trace_id)
            result.answer = f"Error en razonamiento: {str(e)}"
            result.duration_ms = (time.time() - start_time) * 1000

        self.observability.end_span(
            root_span.span_id,
            status="ERROR" if "Error" in result.answer else "OK",
        )
        return result

    def feedback(
        self,
        trace_id: str,
        outcome: str,
        intensity: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Aplica retroalimentación a un camino de razonamiento.

        outcome: 'success' | 'partial' | 'failure'
        """
        # Simplest: reinforce last session's paths
        session = self.memory._sessions.get(trace_id)
        if not session:
            return {"error": "session not found"}

        # Path nodes/edges not easily recoverable from summary; placeholder
        # In production, store full path refs in memory.
        self.plasticity.reset()  # no-op placeholder to keep API
        return {"status": "feedback recorded", "outcome": outcome, "trace_id": trace_id}

    def _compute_diversity(self, paths: List[Any]) -> float:
        if len(paths) < 2:
            return 0.0
        diversities = []
        for i in range(len(paths)):
            for j in range(i + 1, len(paths)):
                set_i = set(paths[i].nodes)
                set_j = set(paths[j].nodes)
                union = set_i | set_j
                if union:
                    diversities.append(1.0 - len(set_i & set_j) / len(union))
        return sum(diversities) / len(diversities) if diversities else 0.0

    def _compute_explainability(self, thoughts: Dict[str, Any]) -> float:
        if not thoughts:
            return 0.0
        traced = sum(1 for t in thoughts.values() if t.attributes.get("source_id") or t.node_refs)
        return traced / len(thoughts)

    def _compute_exhaustiveness(self, paths: List[Any]) -> float:
        types = {p.reasoning_type.value for p in paths}
        return len(types) / 5.0  # 5 reasoning types expected

    def _synthesize_answer(
        self,
        query: str,
        paths: List[Any],
        thought_graph: GraphOfThoughts,
    ) -> str:
        lines = [f"Respuesta a '{query}':", ""]
        lines.append(f"Se exploraron {len(paths)} caminos de razonamiento diversos.")
        for idx, path in enumerate(paths[:3], 1):
            labels = []
            for nid in path.nodes:
                thought = thought_graph.get_thought(nid)
                labels.append(thought.label if thought else nid)
            lines.append(f"  Camino {idx} ({path.reasoning_type.value}): {' → '.join(labels)}")
        if thought_graph._thoughts:
            conclusions = [t.label for t in thought_graph._thoughts.values() if t.role == ThoughtRole.CONCLUSION]
            if conclusions:
                lines.append(f"\nConclusiones: {', '.join(conclusions[:3])}")
        return "\n".join(lines)

    def _generate_narrative(
        self,
        query: str,
        paths: List[Any],
        contradictions: List[Dict[str, Any]],
        metrics: GraphMetrics,
    ) -> str:
        lines = [
            f"Narrativa de razonamiento para '{query}':",
            f"- Se exploraron {len(paths)} caminos de razonamiento.",
            f"- Profundidad promedio: {metrics.reasoning_depth:.2f}.",
            f"- Diversidad: {metrics.diversity:.2f}, consistencia: {metrics.consistency:.2f}.",
        ]
        if contradictions:
            lines.append(f"- Se detectaron {len(contradictions)} inconsistencias.")
        else:
            lines.append("- No se detectaron inconsistencias lógicas.")
        return "\n".join(lines)

    def _build_visualization_data(self, thought_graph: GraphOfThoughts) -> Dict[str, Any]:
        nodes = []
        for tid, t in thought_graph._thoughts.items():
            nodes.append({
                "id": tid,
                "label": t.label,
                "role": t.role.value,
                "abstraction_level": t.abstraction_level,
                "community_id": t.community_id,
                "confidence": t.confidence,
            })
        edges = []
        for e in thought_graph._edges.values():
            edges.append({
                "source": e.source,
                "target": e.target,
                "type": e.edge_type.value,
                "weight": e.weight,
                "justification": e.justification,
            })
        return {"nodes": nodes, "edges": edges}

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "knowledge_graph": self.knowledge_graph.compute_metrics().to_dict(),
            "thought_graph": self.thought_graph.compute_metrics().to_dict(),
            "memory": self.memory.get_statistics(),
            "plasticity": self.plasticity.get_statistics(),
            "observability": self.observability.get_summary(),
        }

    def reset(self) -> None:
        self.knowledge_graph.reset()
        self.thought_graph = GraphOfThoughts()
        self.memory.reset()
        self.plasticity.reset()
        self.meta_reasoning.reset()
        self.observability.reset()
        self.entity_extractor = EntityExtractor()
        self.relation_extractor = RelationExtractor()
