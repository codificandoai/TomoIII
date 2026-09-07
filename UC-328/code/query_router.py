"""
UC-328 — Router de Consultas para ORQUESTA-R.

Descompone consultas en subconsultas atómicas, planifica ejecución y
asigna fuentes según score de idoneidad, costo, latencia y confiabilidad.
"""

from typing import List, Dict, Any, Optional

from orquesta_models import Subquery, Source


class QueryRouter:
    """
    Descompone y enruta consultas.

    Responsabilidades:
    - Descomponer query en subconsultas atómicas.
    - Determinar capacidades requeridas por subconsulta.
    - Asignar fuentes candidatas según puntuación.
    - Ordenar subconsultas por prioridad y dependencias.
    """

    def __init__(self):
        self._capability_map: Dict[str, List[str]] = {
            "fundamental": ["fundamental", "financial_reports", "sec_filings", "earnings"],
            "sentiment": ["sentiment", "social_media", "twitter"],
            "news": ["news", "news_api", "rss", "financial_news"],
            "technical": ["technical", "market_data", "price_history", "indicators"],
            "regulatory": ["regulatory", "sec", "sec_filings", "compliance"],
            "macro": ["macro", "economic_data", "fed", "indicators"],
        }

    def decompose(self, query: str, context: str = "") -> List[Subquery]:
        """
        Descompone una consulta en subconsultas atómicas.

        Heurística basada en palabras clave del query y contexto.
        """
        subqueries = []
        text = (query + " " + context).lower()

        # Detect dimensions
        dimensions = []
        for dim, keywords in self._capability_map.items():
            if any(kw in text for kw in keywords):
                dimensions.append(dim)

        # If no dimensions, treat whole query as single subquery
        if not dimensions:
            dimensions = ["general"]

        for dim in dimensions:
            sub = Subquery(
                text=f"{dim}: {query}",
                priority=0.8 if dim in ["fundamental", "news", "sentiment"] else 0.5,
                required_capabilities=[dim],
            )
            subqueries.append(sub)

        # Add a synthesis subquery
        subqueries.append(Subquery(
            text=f"synthesize: {query}",
            priority=1.0,
            required_capabilities=["synthesis"],
            dependencies=[s.subquery_id for s in subqueries[:-1]],
        ))

        return subqueries

    def select_sources(
        self,
        subquery: Subquery,
        candidates: List[Source],
        latency_map: Optional[Dict[str, float]] = None,
        reliability_boost: float = 1.0,
    ) -> List[Source]:
        """
        Selecciona y ordena fuentes candidatas para una subconsulta.

        Score = confiabilidad / (costo * latencia).
        """
        latency_map = latency_map or {}
        scored = []
        for source in candidates:
            if subquery.required_capabilities and not all(
                cap in source.capabilities for cap in subquery.required_capabilities
            ):
                continue
            latency = latency_map.get(source.source_id, source.base_latency_ms)
            cost = source.cost_per_call + 0.001
            score = (source.reliability * reliability_boost) / (cost * max(1.0, latency))
            scored.append((score, source))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in scored]

    def estimate_complexity(self, subquery: Subquery) -> int:
        """Estima complejidad de una subconsulta en términos simples."""
        return len(subquery.text.split())

    def get_statistics(self) -> Dict[str, Any]:
        """Retorna estadísticas del router."""
        return {
            "capability_map_dimensions": len(self._capability_map),
            "dimensions": list(self._capability_map.keys()),
        }

    def reset(self) -> None:
        """Limpia configuración."""
        pass
