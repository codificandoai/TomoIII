"""Tests del simulador de recompensas turísticas."""
from __future__ import annotations

from environment import TourismRewardSimulator
from models import TravelerContext


def test_solo_culture_prefers_museum() -> None:
    sim = TourismRewardSimulator()
    ctx = TravelerContext(
        user_id="u1",
        group_type="solo",
        age_group="adult",
        season="winter",
        budget_level="medium",
        interests=["culture"],
        mood="curious",
    )
    reward_museum = sim.reward(ctx, "Museo")
    reward_party = sim.reward(ctx, "Compras")
    assert reward_museum > reward_party


def test_family_prefers_adventure_over_museum() -> None:
    sim = TourismRewardSimulator()
    ctx = TravelerContext(
        user_id="u2",
        group_type="family",
        age_group="adult",
        season="summer",
        budget_level="medium",
        interests=["fun"],
        mood="relaxed",
    )
    reward_adv = sim.reward(ctx, "Aventura")
    reward_museum = sim.reward(ctx, "Museo")
    assert reward_adv > reward_museum
