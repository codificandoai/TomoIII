"""Tests de los nodos cognitivos."""
from __future__ import annotations

from config import AgentConfig, AppConfig, get_config
from cognitive_nodes import CognitiveNodes
from evolution import EvolutionEngine
from memory import LongTermMemory
from models import TravelRequest
from safety import SafetyGuard
from state import GenericAIState
from world_simulator import WorldSimulator


def _nodes() -> CognitiveNodes:
    config = get_config()
    return CognitiveNodes(
        LongTermMemory(config.memory.path),
        WorldSimulator(config.world),
        EvolutionEngine(WorldSimulator(config.world), config.evolution),
        SafetyGuard(config.agent),
        config.agent,
    )


def _state(**overrides) -> GenericAIState:
    defaults = {
        "request": TravelRequest(
            origin="Madrid",
            destination="Barcelona",
            departure_date="2026-09-15",
            return_date="2026-09-17",
            budget=2000.0,
            user_id="cog-user",
            preferences={"airline": "Delta"},
            long_term_goals=["Mantener estatus Platino"],
        ).to_state(),
        "user_id": "cog-user",
        "thread_id": "",
        "memory_context": {},
        "beliefs": [],
        "desires": [],
        "intentions": [],
        "reasoning_chain": [],
        "population": [],
        "generation": 0,
        "best_candidate": None,
        "self_critique": "",
        "human_feedback": "",
        "approved_alternative": "",
        "final_plan": [],
        "itinerary": [],
        "reflections": [],
        "logs": [],
        "status": "memory",
        "final_output": None,
        "error_count": 0,
        "retry_count": 0,
        "max_retries": 3,
        "safety_flags": [],
        "missing_info": [],
        "user_confirmed": True,
        "requires_confirmation": False,
        "evolution_stats": {},
        "audit_trail": [],
    }
    defaults.update(overrides)
    return defaults  # type: ignore[return-value]


def test_input_and_memory_node_loads_profile() -> None:
    nodes = _nodes()
    state = _state()
    result = nodes.input_and_memory_node(state)
    assert result["status"] == "evolving"
    assert "preferences" in result["memory_context"]
    assert len(result["beliefs"]) >= 0


def test_self_reflection_detects_contradiction() -> None:
    nodes = _nodes()
    # Simular un mejor candidato que no incluye aerolínea Delta
    state = _state(
        best_candidate={
            "agent_id": "ag-001",
            "genome": {"weights": {"cost": 1.0}},
            "plan": [
                {
                    "item_type": "flight",
                    "id": "FL-1",
                    "action": "Outbound flight",
                    "details": {"airline": "AA", "direct": True, "duration_minutes": 90},
                    "cost": 100,
                }
            ],
            "evaluation": {"fitness": 0.5},
        },
        memory_context={
            "long_term_goals": ["Mantener estatus Platino"],
            "learned_rules": [],
        },
    )
    result = nodes.self_reflection_node(state)
    assert result["status"] == "collaborating"
    assert "Delta" in result["self_critique"]


def test_meta_learning_updates_profile() -> None:
    nodes = _nodes()
    state = _state(
        final_plan=[
            {"item_type": "flight", "id": "FL-1", "cost": 150, "details": {"airline": "Delta"}}
        ],
        best_candidate={
            "agent_id": "ag-001",
            "genome": {"weights": {"cost": 0.2}},
            "evaluation": {"fitness": 0.8},
        },
        human_feedback="Prefiero opciones seguras y salir temprano",
    )
    result = nodes.meta_learning_node(state)
    assert result["status"] == "done"
    profile = nodes.memory.get_profile("cog-user")
    assert len(profile.learned_rules) > 0 or len(profile.policy_archive) > 0
