"""Tests del grafo LangGraph y funciones de entrenamiento."""
from __future__ import annotations

from config import AppConfig, get_config
from graph import recommend, train
from models import TravelerContext


def test_recommend_returns_action() -> None:
    ctx = TravelerContext(
        user_id="test",
        group_type="solo",
        age_group="adult",
        season="winter",
        budget_level="medium",
        interests=["culture"],
        mood="curious",
    )
    result = recommend(ctx, get_config())
    assert result["status"] == "done"
    assert result["last_action"] in get_config().agent.actions
    assert "final_q_values" in result


def test_train_improves_stats() -> None:
    contexts = [
        {"group_type": "solo", "age_group": "adult", "season": "winter", "budget_level": "medium", "interests": ["culture"], "mood": "curious"},
        {"group_type": "family", "age_group": "adult", "season": "summer", "budget_level": "medium", "interests": ["fun"], "mood": "relaxed"},
        {"group_type": "couple", "age_group": "adult", "season": "autumn", "budget_level": "high", "interests": ["food"], "mood": "romantic"},
    ]
    result = train(contexts, episodes=5, config=get_config())
    assert result["status"] == "done"
    assert result["stats"]["episodes"] == 5
    assert result["stats"]["total_reward"] is not None
    assert result["learner_stats"]["experiences"] > 0
