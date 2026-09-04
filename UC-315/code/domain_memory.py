"""UC-315 — Memoria separada por dominio.

Cada dominio (trading, reservations) tiene su propio espacio de memoria lógica y
física: working, episódica, estructurada y vectorial. No se comparten datos ni
credenciales entre dominios.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from long_term_memory import LongTermMemory
from memory_config import MemoryConfig
from memory_router import IntelligentMemoryRouter
from memory_types import MemoryResult
from short_term_memory import ShortTermNotepad
from structured_memory import StructuredMemory


@dataclass
class PlanTemplate:
    name: str
    domain: str
    steps: List[str]
    required_skills: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "domain": self.domain,
            "steps": self.steps,
            "required_skills": self.required_skills,
        }


class DomainMemoryManager:
    """Gestiona memoria aislada por dominio."""

    def __init__(self, domain: str, base_path: Optional[str] = None) -> None:
        self.domain = domain
        self.base_path = base_path or os.path.dirname(__file__)
        self.config = self._build_config()
        self.router = IntelligentMemoryRouter(self.config)
        self._templates: Dict[str, PlanTemplate] = {}
        self._load_default_templates()

    def _build_config(self) -> MemoryConfig:
        config = MemoryConfig()
        # Aislamiento físico: prefijo de dominio en bases de datos y stores
        config.structured.db_path = os.path.join(self.base_path, f"uc315_{self.domain}_memory.db")
        config.vector.store_path = os.path.join(self.base_path, f"uc315_{self.domain}_vectors.json")
        return config

    def _load_default_templates(self) -> None:
        if self.domain == "reservations":
            self._templates["transport_booking"] = PlanTemplate(
                name="transport_booking",
                domain="reservations",
                steps=[
                    "Validar origen, destino, fechas y preferencias",
                    "Consultar opciones disponibles",
                    "Filtrar por restricciones de precio, horario y política",
                    "Seleccionar una opción",
                    "Confirmar condiciones y consentimiento de pago",
                    "Ejecutar la reserva",
                    "Verificar confirmación y registrar el resultado",
                ],
                required_skills=["IdentityValidationSkill", "FlightBookingSkill", "RailBookingSkill", "PaymentSkill", "NotificationSkill"],
            )
        elif self.domain == "trading":
            self._templates["order_lifecycle"] = PlanTemplate(
                name="order_lifecycle",
                domain="trading",
                steps=[
                    "Ingestar datos de mercado",
                    "Generar señal predictiva",
                    "Calcular riesgo y exposición",
                    "Validar orden contra límites",
                    "Autorizar ejecución",
                    "Enviar orden al mercado",
                    "Verificar fill y registrar resultado",
                ],
                required_skills=["MarketDataSkill", "MarketPredictionSkill", "FinancialRiskSkill", "MarketExecutionSkill"],
            )

    def store_working(self, note: str, note_type: str = "working") -> None:
        self.router.store_working_memory(note, note_type=note_type, metadata={"domain": self.domain})

    def retrieve_template(self, name: str) -> Optional[PlanTemplate]:
        return self._templates.get(name)

    def list_templates(self) -> List[Dict[str, Any]]:
        return [t.to_dict() for t in self._templates.values()]

    def retrieve_similar_template(self, query: str) -> Optional[PlanTemplate]:
        """Recuperación semántica simulada: compara keywords del objetivo."""
        query_lower = query.lower()
        best: Optional[PlanTemplate] = None
        best_score = 0
        for template in self._templates.values():
            score = sum(1 for word in ["reserva", "vuelo", "tren", "booking", "order", "trade", "mercado"] if word in query_lower and word in " ".join(template.steps).lower())
            if score > best_score:
                best_score = score
                best = template
        return best

    def retrieve(self, query: str, context: Optional[Dict[str, Any]] = None) -> MemoryResult:
        return self.router.retrieve(query, context)

    def store_episode(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        self.router.vector.add(text, metadata={"domain": self.domain, **(metadata or {})})
