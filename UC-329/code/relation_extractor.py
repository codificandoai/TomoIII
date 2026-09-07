"""
UC-329 — Extractor de Relaciones para GraphRAG-GoT.

Extrae relaciones (sujeto-predicado-objeto) entre entidades usando
heurísticas de proximidad y patrones de texto simples.
"""

import re
from typing import List, Dict, Any, Optional

from graph_models import GraphEdge, GraphNode, EdgeType


class RelationExtractor:
    """
    Extractor de relaciones simple.

    Detecta conectores causales, jerárquicos, temporales y comparativos
    entre entidades que aparecen en la misma oración.
    """

    PATTERNS = {
        EdgeType.CAUSES: [
            "causa", "causan", "produce", "producen", "genera", "generan", "lead to", "leads to",
            "resulta", "resultan", "results in", "causes", "caused", "produces", "generates",
            "gives rise to", "triggers", "creates",
        ],
        EdgeType.PART_OF: ["parte de", "es parte de", "pertenece a", "componente de", "part of", "component of"],
        EdgeType.IS_A: ["es un", "es una", "es el", "es la", "is a", "is an", "is the"],
        EdgeType.SIMILAR_TO: ["similar a", "similar to", "como", "parecido a", "equivalente a", "like"],
        EdgeType.CONTRADICTS: ["contradice", "contradice a", "contradict", "contradicts", "opuesto a", "opposes"],
        EdgeType.SUPPORTS: [
            "soporta", "respaldado por", "supported by", "evidencia de", "evidence of",
            "supports", "reduces", "decreases", "lowers", "improves", "increases", "helps", "enables",
        ],
        EdgeType.REFUTES: ["refuta", "refuta a", "refutes", "desmiente", "debunks", "denies"],
        EdgeType.BEFORE: ["antes de", "before", "anterior a", "previo a", "prior to"],
        EdgeType.AFTER: ["después de", "after", "posterior a", "siguiente a", "following"],
    }

    def __init__(self):
        self._relation_counts: Dict[str, int] = {}

    def extract_relations(
        self,
        text: str,
        entities: List[GraphNode],
        source_id: Optional[str] = None,
    ) -> List[GraphEdge]:
        """
        Extrae relaciones entre entidades presentes en el mismo texto.

        Heurística simple: si dos entidades aparecen en la misma oración
        y hay un conector entre ellas, se crea una arista.
        """
        edges = []
        entity_map = {e.label.lower(): e for e in entities}
        sentences = [s.strip() for s in re.split(r"[.!?\n]", text) if s.strip()]

        for sentence in sentences:
            sent_lower = sentence.lower()
            present = [e for e in entities if e.label.lower() in sent_lower]

            for edge_type, patterns in self.PATTERNS.items():
                for pattern in patterns:
                    if pattern.lower() in sent_lower:
                        for src in present:
                            for tgt in present:
                                if src.node_id == tgt.node_id:
                                    continue
                                # Check pattern lies between them in sentence
                                if self._pattern_between(sentence, src.label, tgt.label, pattern):
                                    edge = GraphEdge(
                                        source=src.node_id,
                                        target=tgt.node_id,
                                        edge_type=edge_type,
                                        weight=1.0,
                                        attributes={"context": sentence[:200]},
                                        source_id=source_id,
                                    )
                                    edges.append(edge)
                                    key = f"{edge_type.value}"
                                    self._relation_counts[key] = self._relation_counts.get(key, 0) + 1
        return edges

    def _pattern_between(
        self,
        sentence: str,
        source_label: str,
        target_label: str,
        pattern: str,
    ) -> bool:
        """Verifica si el patrón está entre dos entidades en la oración."""
        lower = sentence.lower()
        src_pos = lower.find(source_label.lower())
        tgt_pos = lower.find(target_label.lower())
        pat_pos = lower.find(pattern.lower())
        if src_pos == -1 or tgt_pos == -1 or pat_pos == -1:
            return False
        return (src_pos < pat_pos < tgt_pos) or (tgt_pos < pat_pos < src_pos)

    def get_statistics(self) -> Dict[str, Any]:
        """Retorna estadísticas de extracción."""
        return {
            "relation_counts": dict(self._relation_counts),
            "total_distinct_relation_types": len(self._relation_counts),
        }
