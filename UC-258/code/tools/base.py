"""Interfaz base para herramientas externas."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict

from models import ExternalData


class ExternalTool(ABC):
    """Conector intercambiable para datos externos verificables."""

    name: str = ""

    @abstractmethod
    def call(self, **kwargs: Any) -> ExternalData:
        ...

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name}
