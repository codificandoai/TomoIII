"""Simulador de recompensas del entorno turístico para UC-263."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from models import TravelerContext


class TourismRewardSimulator:
    """Simula la retroalimentación del entorno ante una recomendación.

    En producción esta recompensa provendría del usuario (clics, reservas,
    encuestas). En el ejemplo codificamos unas preferencias ocultas para que
    el agente aprenda por ensayo y error.
    """

    # Preferencias ocultas que el agente debe descubrir
    _PREFERENCES: Dict[str, Dict[str, float]] = {
        "solo": {
            "culture": {"Museo": 1.0, "Evento cultural": 0.9, "Gastronomía": 0.5, "Aventura": 0.3, "Descanso": 0.2},
            "nature": {"Naturaleza": 1.0, "Aventura": 0.8, "Playa": 0.5, "Museo": 0.3},
        },
        "couple": {
            "romantic": {"Gastronomía": 1.0, "Playa": 0.8, "Evento cultural": 0.6, "Aventura": 0.5, "Museo": 0.3},
            "adventure": {"Aventura": 1.0, "Naturaleza": 0.9, "Playa": 0.6, "Descanso": 0.1},
        },
        "family": {
            "fun": {"Aventura": 1.0, "Playa": 0.9, "Museo": 0.5, "Compras": 0.4, "Gastronomía": 0.4},
            "culture": {"Museo": 1.0, "Evento cultural": 0.8, "Aventura": 0.5, "Playa": 0.4},
        },
        "friends": {
            "party": {"Gastronomía": 1.0, "Aventura": 0.9, "Playa": 0.8, "Compras": 0.6, "Descanso": 0.1},
            "culture": {"Evento cultural": 0.9, "Museo": 0.7, "Gastronomía": 0.5},
        },
    }

    # Ajustes por estación
    _SEASON_MODIFIERS: Dict[str, Dict[str, float]] = {
        "summer": {"Playa": 0.25, "Aventura": 0.1, "Naturaleza": 0.1},
        "winter": {"Museo": 0.15, "Gastronomía": 0.15, "Evento cultural": 0.1},
        "spring": {"Naturaleza": 0.2, "Museo": 0.1, "Aventura": 0.1},
        "autumn": {"Gastronomía": 0.2, "Evento cultural": 0.1, "Naturaleza": 0.1},
    }

    def __init__(self, actions: Optional[List[str]] = None) -> None:
        self.actions = actions or [
            "Museo",
            "Aventura",
            "Gastronomía",
            "Descanso",
            "Playa",
            "Naturaleza",
            "Compras",
            "Evento cultural",
        ]

    def reward(
        self,
        context: TravelerContext,
        action: str,
        noise: float = 0.05,
    ) -> float:
        """Devuelve una recompensa en [-1, 1]."""
        import numpy as np

        group = context.group_type if context.group_type in self._PREFERENCES else "solo"
        # Elegir sub-perfil por intereses o estado de ánimo
        profile_keys = list(self._PREFERENCES[group].keys())
        sub_profile = self._infer_sub_profile(context, profile_keys)
        base = self._PREFERENCES[group][sub_profile].get(action, 0.0)

        # Ajuste por estación
        season_mod = self._SEASON_MODIFIERS.get(context.season, {}).get(action, 0.0)

        # Ajuste por intereses explícitos del usuario
        interest_bonus = 0.0
        if context.interests:
            interest_bonus = self._interest_bonus(context.interests, action)

        # Presupuesto
        budget_bonus = 0.0
        if context.budget_level == "low" and action in ("Gastronomía", "Compras"):
            budget_bonus = -0.15
        if context.budget_level == "high" and action in ("Descanso", "Gastronomía"):
            budget_bonus = 0.1

        # Niños -> Aventura/Playa mejores, Museo/Evento cultural algo peor
        kids_bonus = 0.0
        if context.age_group == "child" and action in ("Aventura", "Playa"):
            kids_bonus = 0.2

        score = base + season_mod + interest_bonus + budget_bonus + kids_bonus
        # Normalizar a [-1, 1]
        score = max(-1.0, min(1.0, score))
        # Ruido gaussiano pequeño
        rng = np.random.default_rng(hash(context.describe() + action) % 2**32)
        score += float(rng.normal(0, noise))
        return round(max(-1.0, min(1.0, score)), 4)

    def _infer_sub_profile(self, context: TravelerContext, keys: List[str]) -> str:
        text = " ".join(context.interests + [context.mood]).lower()
        for key in keys:
            if key in text:
                return key
        # Fallback por estado de ánimo
        mood_map = {
            "romantic": "romantic",
            "party": "party",
            "relaxed": "fun",
            "adventurous": "adventure",
            "cultural": "culture",
            "fun": "fun",
        }
        for mood, mapped in mood_map.items():
            if mood in context.mood.lower() and mapped in keys:
                return mapped
        return keys[0]

    def _interest_bonus(self, interests: List[str], action: str) -> float:
        mapping = {
            "culture": ["Museo", "Evento cultural"],
            "history": ["Museo", "Evento cultural"],
            "art": ["Museo", "Evento cultural"],
            "adventure": ["Aventura", "Naturaleza"],
            "nature": ["Naturaleza", "Playa"],
            "beach": ["Playa"],
            "food": ["Gastronomía"],
            "gastronomy": ["Gastronomía"],
            "shopping": ["Compras"],
            "relax": ["Descanso"],
        }
        bonus = 0.0
        for interest in interests:
            if action in mapping.get(interest.lower(), []):
                bonus += 0.15
        return min(0.3, bonus)
