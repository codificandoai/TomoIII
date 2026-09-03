"""Tests del punto de entrada unificado brain.py."""
from __future__ import annotations

import brain


def test_demo_sam():
    result = brain.demo_sam()
    assert result["mode"] == "sam"
    assert "metacognition" in result
    assert result["metacognition"]["recommendation"] in ("PROCEED", "REVIEW", "ABORT")


def test_demo_tot():
    result = brain.demo_tot(use_brain=False)
    assert result["mode"] == "tot"
    assert result["status"] == "ok"
    final = result["final_prediction"]
    assert final["predicted_ask"] > final["predicted_bid"] > 0.0
    assert result["tree_summary"]["success_leaves"] >= 1


def test_demo_full_agi():
    result = brain.demo_full_agi()
    assert result["mode"] == "full_agi"
    assert "trading" in result
    assert "tot" in result
    assert result["tot"]["final_prediction"]["predicted_ask"] > 0.0


def test_main_cli():
    # Verifica que main() pueda ejecutarse sin excepciones en modo sam.
    assert brain.main(["--mode", "sam"]) == 0
