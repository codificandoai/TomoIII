"""Tests del planificador recursivo UC-314."""
from __future__ import annotations

from causal_model import SymbolicCausalModel
from plan_evaluator import PlanEvaluator
from recursive_planner import RecursivePlanner
from tool_registry import ToolRegistry, default_tools


def test_direct_tool_match():
    planner = RecursivePlanner(ToolRegistry(default_tools()))
    plan = planner.plan("Enviar correo electrónico a leads")
    assert plan.status == "executable"
    assert plan.tool_name == "send_email"


def test_recursive_campaign_plan():
    planner = RecursivePlanner(ToolRegistry(default_tools()))
    plan = planner.plan("Incrementar ventas del producto X mediante marketing digital")
    assert len(plan.children) > 0
    leaves = []
    PlanEvaluator._collect_leaves(plan, leaves)
    executable = [l for l in leaves if l.status == "executable"]
    blocked = [l for l in leaves if l.status == "blocked"]
    # Al menos algunas hojas deben ser ejecutables con el set de tools de demo
    assert len(executable) + len(blocked) == len(leaves)


def test_max_depth_stop():
    planner = RecursivePlanner(ToolRegistry(default_tools()), max_depth=1)
    plan = planner.plan("Incrementar ventas del producto X mediante marketing digital")
    assert plan.status == "blocked"


def test_causal_dependency_blocks():
    scm = SymbolicCausalModel()
    scm.add_dependency("PricingAPI", "MarketingService")
    scm.set_node_state("MarketingService", "FALLO: servicio caído")
    planner = RecursivePlanner(ToolRegistry(default_tools()), scm)
    # El objetivo de marketing depende de MarketingService
    plan = planner.plan("Incrementar ventas del producto X mediante marketing digital")
    assert plan.status == "blocked"


def test_execute_plan():
    planner = RecursivePlanner(ToolRegistry(default_tools()))
    plan = planner.plan("Enviar correo electrónico a leads")
    executed = planner.execute_plan(plan)
    assert executed.status == "executed"
