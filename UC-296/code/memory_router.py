"""Enrutador inteligente de memoria: decide qué subsistema consultar."""
from __future__ import annotations

import time
from typing import Any, Dict, Optional

from long_term_memory import LongTermMemory
from memory_config import MemoryConfig
from memory_types import MemoryIntent, MemoryResult
from short_term_memory import ShortTermNotepad
from structured_memory import StructuredMemory


class IntelligentMemoryRouter:
    """Árbitro que clasifica la intención de una consulta y la enruta al
    subsistema de memoria adecuado: bloc de notas (corto plazo), SQL
    (estructurado) o vectorial (semántico). También expone `self_model` para
    recuperar el autoconocimiento persistente del agente.
    """

    def __init__(self, config: Optional[MemoryConfig] = None) -> None:
        self.config = config or MemoryConfig()
        self.notepad = ShortTermNotepad(self.config.short_term)
        self.structured = StructuredMemory(self.config.structured)
        self.vector = LongTermMemory(self.config.vector)
        self._ensure_demo_facts()

    def _ensure_demo_facts(self) -> None:
        """Carga hechos de demostración si aún no existen."""
        if self.structured.query("products", "SKU-001", "cost") is None:
            self.structured.store("products", "SKU-001", "cost", 100.0)
            self.structured.store("products", "SKU-001", "stock", 450)
            self.structured.store("products", "SKU-002", "cost", 45.5)
            self.structured.store("products", "SKU-002", "stock", 1200)
            self.structured.store("users", "U-99", "role", "Pricing_Manager")

    def classify_intent(self, query: str) -> MemoryIntent:
        q = query.lower()
        sql_triggers = [
            "costo de", "inventario de", "precio actual de", "perfil del",
            "cuántos", "dame el", "stock de", "valor de", "sku-", "u-", "id-",
        ]
        if any(t in q for t in sql_triggers):
            return MemoryIntent.FACTUAL_LOOKUP
        notepad_triggers = [
            "acabo de", "paso anterior", "resultado actual", "último cálculo",
            "memoria inmediata", "última acción", "última decisión",
        ]
        if any(t in q for t in notepad_triggers):
            return MemoryIntent.WORKING_STATE
        self_triggers = [
            "mi objetivo", "mi meta", "current_goal", "self-model", "autoconocimiento",
            "capacidades", "límites operativos", "historial de desempeño",
        ]
        if any(t in q for t in self_triggers):
            return MemoryIntent.SELF_MODEL
        return MemoryIntent.SEMANTIC_RECALL

    def retrieve(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> MemoryResult:
        intent = self.classify_intent(query)
        start = time.time()
        context = context or {}

        if intent == MemoryIntent.WORKING_STATE:
            return MemoryResult(
                intent=intent,
                source="ShortTermNotepad",
                data=self.notepad.retrieve_latest_text(n=5),
                latency_ms=(time.time() - start) * 1000,
                confidence=1.0,
                metadata={"size": len(self.notepad._notes)},
            )

        if intent == MemoryIntent.FACTUAL_LOOKUP:
            entity_type = context.get("entity_type") or self._infer_entity_type(query)
            entity_id = context.get("entity_id") or self._infer_entity_id(query)
            attribute = context.get("attribute") or self._infer_attribute(query)
            if entity_type and entity_id and attribute:
                value = self.structured.query(entity_type, entity_id, attribute)
                return MemoryResult(
                    intent=intent,
                    source="StructuredMemory (SQLite/pgvector)",
                    data={attribute: value},
                    latency_ms=(time.time() - start) * 1000,
                    confidence=1.0 if value is not None else 0.0,
                    metadata={"entity_type": entity_type, "entity_id": entity_id},
                )
            return MemoryResult(
                intent=intent,
                source="StructuredMemory (SQLite/pgvector)",
                data="Error: Parámetros faltantes para consulta estructurada.",
                latency_ms=(time.time() - start) * 1000,
                confidence=0.0,
            )

        if intent == MemoryIntent.SELF_MODEL:
            model = self.structured.get_self_model()
            if model:
                return MemoryResult(
                    intent=intent,
                    source="StructuredMemory (SelfModel)",
                    data=model,
                    latency_ms=(time.time() - start) * 1000,
                    confidence=1.0,
                )
            return MemoryResult(
                intent=intent,
                source="StructuredMemory (SelfModel)",
                data="No hay self-model persistente todavía.",
                latency_ms=(time.time() - start) * 1000,
                confidence=0.0,
            )

        return self.vector.retrieve(query)

    def store_working_memory(
        self,
        content: str,
        note_type: str = "general",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.notepad.store(content, note_type=note_type, metadata=metadata)

    def store_episode(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        return self.vector.add(text, metadata=metadata)

    @staticmethod
    def _infer_entity_type(query: str) -> Optional[str]:
        q = query.lower()
        if "sku" in q:
            return "products"
        if "u-" in q or "usuario" in q or "user" in q:
            return "users"
        return None

    @staticmethod
    def _infer_entity_id(query: str) -> Optional[str]:
        for token in query.upper().split():
            if token.startswith("SKU-"):
                return token
            if token.startswith("U-"):
                return token
        return None

    @staticmethod
    def _infer_attribute(query: str) -> Optional[str]:
        q = query.lower()
        if "costo" in q:
            return "cost"
        if "inventario" in q or "stock" in q:
            return "stock"
        if "rol" in q or "perfil" in q:
            return "role"
        if "permisos" in q:
            return "permissions"
        return None
