"""Interfaz abstracta base para todos los entornos."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict

from models import EnvironmentProperties, Observation, StepResult


class Environment(ABC):
    """Contrato mínimo que todo entorno debe cumplir."""

    @property
    @abstractmethod
    def properties(self) -> EnvironmentProperties:
        ...

    @abstractmethod
    def get_observation(self) -> Observation:
        """Devuelve la observación disponible para el agente."""
        ...

    @abstractmethod
    def is_valid_action(self, action: Any) -> bool:
        """Valida si una acción es legal en el estado actual."""
        ...

    @abstractmethod
    def step(self, action: Any) -> StepResult:
        """Ejecuta la acción y devuelve resultado, recompensa, done e info."""
        ...

    @abstractmethod
    def reset(self) -> Observation:
        """Reinicia el entorno."""
        ...

    def get_state(self) -> Dict[str, Any]:
        """Devuelve el estado interno completo (solo para debug/audit)."""
        return {}
