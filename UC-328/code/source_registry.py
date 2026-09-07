"""
UC-328 — Registro de Fuentes para ORQUESTA-R.

Permite registrar, descubrir, seleccionar y evaluar fuentes de datos
externas (APIs, bases de datos, vector stores, document stores).
"""

from typing import List, Dict, Optional, Callable, Any

from orquesta_models import Source, SourceType


class SourceRegistry:
    """
    Registro de fuentes de datos del orquestador.

    Responsabilidades:
    - Registrar fuentes con metadata, costos, latencias y confiabilidad.
    - Descubrir fuentes por capacidades o tags.
    - Seleccionar fuentes candidatas para una subconsulta.
    - Gestionar estado habilitado/deshabilitado.
    """

    def __init__(self):
        self._sources: Dict[str, Source] = {}
        self._connectors: Dict[str, Callable[[str, Dict[str, Any]], Any]] = {}

    def register(
        self,
        source: Source,
        connector: Optional[Callable[[str, Dict[str, Any]], Any]] = None,
    ) -> Source:
        """Registra una fuente y opcionalmente su conector."""
        self._sources[source.source_id] = source
        if connector:
            self._connectors[source.source_id] = connector
        return source

    def register_connector(
        self,
        source_id_or_name: str,
        connector: Callable[[str, Dict[str, Any]], Any],
    ) -> bool:
        """
        Registra un conector por source_id o nombre.

        Útil cuando la fuente se registró previamente sin conector.
        """
        if source_id_or_name in self._sources:
            self._connectors[source_id_or_name] = connector
            return True
        for source in self._sources.values():
            if source.name == source_id_or_name:
                self._connectors[source.source_id] = connector
                return True
        return False

    def register_from_dict(
        self,
        data: Dict[str, Any],
        connector: Optional[Callable[[str, Dict[str, Any]], Any]] = None,
    ) -> Source:
        """Registra una fuente a partir de un diccionario."""
        source_type = SourceType(data.get("source_type", "api"))
        source_id = data.get("source_id", "")
        source_kwargs = {
            "name": data.get("name", ""),
            "source_type": source_type,
            "endpoint": data.get("endpoint", ""),
            "cost_per_call": float(data.get("cost_per_call", 0.0)),
            "cost_per_kb": float(data.get("cost_per_kb", 0.0)),
            "base_latency_ms": float(data.get("base_latency_ms", 200.0)),
            "reliability": float(data.get("reliability", 0.9)),
            "rate_limit": int(data.get("rate_limit", 10)),
            "schema": data.get("schema"),
            "capabilities": list(data.get("capabilities", [])),
            "tags": list(data.get("tags", [])),
            "enabled": bool(data.get("enabled", True)),
            "metadata": dict(data.get("metadata", {})),
        }
        if source_id:
            source_kwargs["source_id"] = source_id
        source = Source(**source_kwargs)
        return self.register(source, connector)

    def get(self, source_id: str) -> Optional[Source]:
        """Obtiene una fuente por ID."""
        return self._sources.get(source_id)

    def get_connector(self, source_id: str) -> Optional[Callable]:
        """Obtiene el conector de una fuente."""
        return self._connectors.get(source_id)

    def list_sources(
        self,
        enabled_only: bool = True,
        source_type: Optional[SourceType] = None,
        capability: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> List[Source]:
        """Lista fuentes filtradas."""
        sources = list(self._sources.values())
        if enabled_only:
            sources = [s for s in sources if s.enabled]
        if source_type:
            sources = [s for s in sources if s.source_type == source_type]
        if capability:
            sources = [s for s in sources if capability in s.capabilities]
        if tag:
            sources = [s for s in sources if tag in s.tags]
        return sources

    def find_for_subquery(self, subquery_text: str, required_capabilities: List[str]) -> List[Source]:
        """
        Encuentra fuentes adecuadas para una subconsulta.

        Heurística simple: coincidencia de palabras clave en tags/capabilities.
        """
        candidates = []
        query_words = set(subquery_text.lower().split())
        for source in self.list_sources(enabled_only=True):
            source_words = set(" ".join(source.capabilities + source.tags).lower().split())
            score = len(query_words & source_words)
            if required_capabilities and not all(cap in source.capabilities for cap in required_capabilities):
                continue
            candidates.append((score, source))
        candidates.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in candidates]

    def disable(self, source_id: str) -> bool:
        """Deshabilita una fuente."""
        source = self._sources.get(source_id)
        if source:
            source.enabled = False
            return True
        return False

    def enable(self, source_id: str) -> bool:
        """Habilita una fuente."""
        source = self._sources.get(source_id)
        if source:
            source.enabled = True
            return True
        return False

    def get_statistics(self) -> Dict[str, Any]:
        """Retorna estadísticas del registro."""
        by_type: Dict[str, int] = {}
        for s in self._sources.values():
            by_type[s.source_type.value] = by_type.get(s.source_type.value, 0) + 1
        return {
            "total": len(self._sources),
            "enabled": sum(1 for s in self._sources.values() if s.enabled),
            "by_type": by_type,
            "total_connectors": len(self._connectors),
        }

    def reset(self) -> None:
        """Limpia el registro."""
        self._sources.clear()
        self._connectors.clear()
