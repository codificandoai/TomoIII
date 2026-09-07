"""
UC-329 — Extractor de Entidades para GraphRAG-GoT.

Extrae entidades nombradas y conceptos de texto usando heurísticas
basadas en mayúsculas, patrones numéricos y un vocabulario de dominio.
"""

import re
from typing import List, Dict, Any, Optional

from graph_models import GraphNode, NodeType


class EntityExtractor:
    """
    Extractor de entidades simple (stub para NER).

    Reglas:
    - Palabras en mayúscula consecutivas (nombres propios).
    - Términos numéricos con unidades (precios, porcentajes).
    - Términos del vocabulario de dominio.
    """

    def __init__(self, domain_vocabulary: Optional[List[str]] = None):
        self.domain_vocabulary = set(domain_vocabulary or [])

    def extract(self, text: str, source_id: Optional[str] = None) -> List[GraphNode]:
        """Extrae entidades de un texto."""
        entities = []
        seen = set()

        # Títulos y nombres propios (2+ palabras capitalizadas)
        for match in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", text):
            label = match.group(1)
            if label not in seen:
                seen.add(label)
                entities.append(GraphNode(
                    label=label,
                    node_type=NodeType.ENTITY,
                    attributes={"span": (match.start(), match.end())},
                    source_id=source_id,
                ))

        # Términos del vocabulario de dominio (case-insensitive)
        for term in self.domain_vocabulary:
            pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
            for match in pattern.finditer(text):
                key = term.lower()
                if key not in seen:
                    seen.add(key)
                    entities.append(GraphNode(
                        label=term,
                        node_type=NodeType.CONCEPT,
                        attributes={"span": (match.start(), match.end())},
                        source_id=source_id,
                    ))

        # Números con unidades monetarias o porcentaje
        for match in re.finditer(r"\b(\d+(?:\.\d+)?\s*(?:%|USD|\$|€|£|años?|meses?))\b", text):
            label = match.group(1)
            if label not in seen:
                seen.add(label)
                entities.append(GraphNode(
                    label=label,
                    node_type=NodeType.EVIDENCE,
                    attributes={"span": (match.start(), match.end())},
                    source_id=source_id,
                ))

        return entities

    def add_vocabulary(self, terms: List[str]) -> None:
        """Agrega términos al vocabulario de dominio."""
        for term in terms:
            self.domain_vocabulary.add(term.lower())

    def get_statistics(self) -> Dict[str, Any]:
        """Retorna estadísticas del extractor."""
        return {
            "domain_vocabulary_size": len(self.domain_vocabulary),
            "vocabulary": sorted(self.domain_vocabulary),
        }
