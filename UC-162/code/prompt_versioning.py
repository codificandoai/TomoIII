"""
UC-162 — Versionado y evaluación de prompts.

Mantiene un registro de versiones de prompts con:
- Aprobación por compliance.
- Score de evaluación.
- Tags para categorización.
- Historial de versiones.

Los prompts son parte del modelado lógico: su estructura define
cómo se recupera y presenta el conocimiento al LLM.
"""

import time
import uuid
from typing import Dict, List, Optional, Any

from models_162 import PromptVersion, LLMOpsConfig


class PromptRegistry:
    """Registro de versiones de prompts con aprobación y evaluación."""

    def __init__(self, config: Optional[LLMOpsConfig] = None):
        self.config = config or LLMOpsConfig()
        self.prompts: Dict[str, PromptVersion] = {}
        self.history: List[Dict[str, Any]] = []

    def register(
        self,
        template: str,
        version: str = "",
        tags: List[str] = None,
    ) -> PromptVersion:
        """Registra una nueva versión de prompt."""
        if not version:
            version = f"v{len(self.prompts) + 1}"
        prompt_id = str(uuid.uuid4())
        prompt = PromptVersion(
            id=prompt_id,
            template=template,
            version=version,
            tags=tags or [],
        )
        self.prompts[prompt_id] = prompt
        self.history.append({
            "action": "registered",
            "prompt_id": prompt_id,
            "version": version,
            "timestamp": time.time(),
        })
        # Limitar historial
        if len(self.prompts) > self.config.max_prompt_versions:
            oldest = list(self.prompts.keys())[0]
            del self.prompts[oldest]
        return prompt

    def approve(
        self,
        prompt_id: str,
        approved_by: str = "compliance_officer",
    ) -> Optional[PromptVersion]:
        """Aprueba una versión de prompt."""
        prompt = self.prompts.get(prompt_id)
        if not prompt:
            return None
        prompt.approved = True
        prompt.approved_by = approved_by
        self.history.append({
            "action": "approved",
            "prompt_id": prompt_id,
            "approved_by": approved_by,
            "timestamp": time.time(),
        })
        return prompt

    def evaluate(
        self,
        prompt_id: str,
        evaluation_score: float,
    ) -> Optional[PromptVersion]:
        """Asigna un score de evaluación al prompt."""
        prompt = self.prompts.get(prompt_id)
        if not prompt:
            return None
        prompt.evaluation_score = max(0.0, min(1.0, evaluation_score))
        self.history.append({
            "action": "evaluated",
            "prompt_id": prompt_id,
            "score": evaluation_score,
            "timestamp": time.time(),
        })
        return prompt

    def get_approved(self) -> List[PromptVersion]:
        """Retorna todos los prompts aprobados."""
        return [p for p in self.prompts.values() if p.approved]

    def get_latest_approved(self) -> Optional[PromptVersion]:
        """Retorna el prompt aprobado más reciente."""
        approved = self.get_approved()
        if not approved:
            return None
        return max(approved, key=lambda p: p.created_at)

    def get_by_version(self, version: str) -> Optional[PromptVersion]:
        """Busca un prompt por su versión."""
        for p in self.prompts.values():
            if p.version == version:
                return p
        return None

    def list_all(self) -> List[Dict[str, Any]]:
        """Lista todos los prompts registrados."""
        return [p.to_dict() for p in self.prompts.values()]

    def get_history(self) -> List[Dict[str, Any]]:
        return self.history

    def reset(self):
        self.prompts.clear()
        self.history.clear()
