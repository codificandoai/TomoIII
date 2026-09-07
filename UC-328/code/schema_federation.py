"""
UC-328 — Federación de Esquemas para ORQUESTA-R.

Normaliza datos provenientes de fuentes heterogéneas hacia un modelo
canónico. Soporta mapeo de tipos, unidades, jerarquías y limpieza de
valores nulos/duplicados.
"""

from typing import Dict, List, Optional, Any
import copy

from orquesta_models import Source


class SchemaFederation:
    """
    Adaptador de esquemas para fuentes de datos heterogéneas.

    Funciones:
    - Mapear campos de esquema fuente a esquema canónico.
    - Normalizar tipos de datos.
    - Limpiar nulos y duplicados.
    - Reutilizar mapeos cacheados por fuente.
    """

    def __init__(self, canonical_model: Optional[Dict[str, str]] = None):
        self.canonical_model = canonical_model or {
            "id": "string",
            "content": "string",
            "value": "number",
            "category": "string",
            "timestamp": "timestamp",
            "source": "string",
            "confidence": "number",
        }
        self._adapters: Dict[str, Dict[str, str]] = {}

    def register_adapter(
        self,
        source_id: str,
        field_mapping: Dict[str, str],
    ) -> None:
        """Registra un mapeo de campos fuente → canónico."""
        self._adapters[source_id] = field_mapping

    def normalize(
        self,
        source: Source,
        data: Any,
    ) -> Dict[str, Any]:
        """
        Normaliza un dato bruto al modelo canónico.

        Si data es dict, aplica mapeo y normalización.
        Si es string, lo coloca en content.
        Si es lista, normaliza cada elemento.
        """
        if data is None:
            return {"content": "", "source": source.name}

        if isinstance(data, list):
            return {
                "items": [self._normalize_item(source, item) for item in data],
                "source": source.name,
            }

        if isinstance(data, dict):
            return self._normalize_item(source, data)

        return {"content": str(data), "source": source.name}

    def _normalize_item(self, source: Source, item: Dict[str, Any]) -> Dict[str, Any]:
        """Normaliza un item individual."""
        mapping = self._adapters.get(source.source_id, {})
        normalized: Dict[str, Any] = {}

        # Apply mapping: canonical field <- source field
        for canonical_field in self.canonical_model.keys():
            if canonical_field in mapping:
                source_field = mapping[canonical_field]
                value = item.get(source_field)
            else:
                value = item.get(canonical_field)
            normalized[canonical_field] = self._coerce_type(canonical_field, value)

        # Add raw source field fallback for content
        if not normalized.get("content") and isinstance(item, dict):
            for k in ["text", "body", "description", "value", "data"]:
                if k in item and item[k]:
                    normalized["content"] = str(item[k])
                    break

        # Add metadata
        normalized["source"] = source.name
        normalized["source_id"] = source.source_id
        normalized["source_type"] = source.source_type.value
        return self._clean(normalized)

    def _coerce_type(self, field: str, value: Any) -> Any:
        """Fuerza tipos canónicos."""
        expected = self.canonical_model.get(field, "string")
        if value is None:
            return None
        try:
            if expected == "number":
                return float(value)
            if expected == "timestamp":
                return str(value)
            if expected == "boolean":
                return bool(value)
            return str(value)
        except (ValueError, TypeError):
            return str(value)

    def _clean(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Limpia nulos y duplicados simples."""
        cleaned = {}
        seen = set()
        for k, v in record.items():
            if v is None:
                cleaned[k] = "unknown"
                continue
            key = f"{k}:{str(v).lower()}"
            if key not in seen:
                seen.add(key)
                cleaned[k] = v
        return cleaned

    def build_adapter_from_schema(
        self,
        source: Source,
    ) -> Dict[str, str]:
        """
        Intenta inferir un mapeo básico a partir del esquema de la fuente.
        """
        if not source.schema:
            return {}

        mapping = {}
        source_fields = set(source.schema.keys())
        for canonical_field in self.canonical_model.keys():
            if canonical_field in source_fields:
                mapping[canonical_field] = canonical_field
            else:
                # Simple synonym matching
                synonyms = self._synonyms(canonical_field)
                for syn in synonyms:
                    if syn in source_fields:
                        mapping[canonical_field] = syn
                        break
        self._adapters[source.source_id] = mapping
        return mapping

    def _synonyms(self, field: str) -> List[str]:
        """Sinónimos de campos canónicos."""
        synonyms = {
            "id": ["id", "identifier", "uuid", "key"],
            "content": ["content", "text", "body", "description", "value", "data"],
            "category": ["category", "type", "label", "class"],
            "timestamp": ["timestamp", "date", "created_at", "updated_at", "time"],
            "source": ["source", "origin", "provider"],
            "confidence": ["confidence", "score", "certainty", "probability"],
        }
        return synonyms.get(field, [field])

    def get_adapter(self, source_id: str) -> Optional[Dict[str, str]]:
        """Obtiene el adaptador de una fuente."""
        return self._adapters.get(source_id)

    def get_statistics(self) -> Dict[str, Any]:
        """Retorna estadísticas de adaptadores registrados."""
        return {
            "canonical_fields": list(self.canonical_model.keys()),
            "registered_adapters": list(self._adapters.keys()),
            "adapter_count": len(self._adapters),
        }

    def reset(self) -> None:
        """Limpia adaptadores."""
        self._adapters.clear()
