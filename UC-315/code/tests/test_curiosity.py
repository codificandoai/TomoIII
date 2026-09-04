"""Tests del bucle de aprendizaje por curiosidad UC-313."""
from __future__ import annotations

from curiosity_skill_loop import CuriositySkillLoop


def test_solves_with_existing_tools():
    loop = CuriositySkillLoop()
    result = loop.metatool_learn_new_skill("Calcula la suma total", 42.0)
    assert result["outcome"] == "solved"
    assert result["generated_skill"] is None


def test_acquires_new_skill_on_failure():
    loop = CuriositySkillLoop()
    # Problema que requiere consultar precio
    result = loop.metatool_learn_new_skill(
        "¿Cuál es el precio actual del SKU-123?", 100.0
    )
    assert result["outcome"] == "solved"
    assert result["generated_skill"] is not None
    assert result["generated_skill"]["name"] == "consultar_precio"


def test_generates_reasonable_hypothesis():
    trigger = CuriositySkillLoop().trigger
    h = trigger.hypothesize("Necesito detectar la tendencia de AAPL", ["sumar"])
    assert "detectar_tendencia" in h["name"]
    assert "def " in h["signature"]


def test_tool_registry_compiles_and_calls():
    from curiosity_skill_loop import Tool
    tool = Tool(
        name="consultar_precio",
        signature="def consultar_precio(sku: str) -> float:",
        code="def consultar_precio(sku: str) -> float:\n    return 100.0\n",
        description="test",
    )
    loop = CuriositySkillLoop()
    loop.registry.register(tool)
    assert loop.registry.has("consultar_precio")
    assert loop.registry.call("consultar_precio", "SKU-1") == 100.0


def test_summary_tracks_attempts():
    loop = CuriositySkillLoop()
    loop.metatool_learn_new_skill("multiplica 3 y 4", 12.0)
    summary = loop.summary()
    assert summary["total_attempts"] >= 1
