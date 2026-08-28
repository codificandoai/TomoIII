"""Tests del HPA Manager."""
from __future__ import annotations

from config import HPAConfig
from hpa_manager import HPAManager
from models import AgentProfile, AgentRole, PodMetrics, ScalingDirection


def _hpa() -> HPAManager:
    config = HPAConfig(
        min_replicas=1,
        max_replicas=10,
        target_cpu_percent=70,
        target_memory_percent=80,
        scale_up_cooldown_sec=0,
        scale_down_cooldown_sec=0,
        custom_metric_target=5,
    )
    return HPAManager(config)


def _profile() -> AgentProfile:
    return AgentProfile(name="worker", role=AgentRole.coder, skill=0.8, cost=1.0, latency_ms=200, replicas=3)


def test_scale_up_on_high_load() -> None:
    hpa = _hpa()
    hpa.register_agent(_profile())
    metrics = PodMetrics(agent_name="worker", cpu_percent=95, memory_percent=90, queue_depth=10, replicas_current=3)
    decision = hpa.evaluate(metrics)
    assert decision.direction == ScalingDirection.up
    assert decision.desired_replicas > 3


def test_scale_down_on_low_load() -> None:
    hpa = _hpa()
    hpa.register_agent(_profile())
    metrics = PodMetrics(agent_name="worker", cpu_percent=10, memory_percent=10, queue_depth=0, replicas_current=3)
    decision = hpa.evaluate(metrics)
    assert decision.direction == ScalingDirection.down
    assert decision.desired_replicas < 3


def test_no_change_on_stable_load() -> None:
    hpa = _hpa()
    hpa.register_agent(_profile())
    metrics = PodMetrics(agent_name="worker", cpu_percent=50, memory_percent=50, queue_depth=3, replicas_current=3)
    decision = hpa.evaluate(metrics)
    assert decision.direction == ScalingDirection.none
    assert decision.desired_replicas == 3


def test_respects_max_replicas() -> None:
    hpa = _hpa()
    hpa.register_agent(_profile())
    metrics = PodMetrics(agent_name="worker", cpu_percent=100, memory_percent=100, queue_depth=50, replicas_current=9)
    decision = hpa.evaluate(metrics)
    assert decision.desired_replicas <= 10


def test_respects_min_replicas() -> None:
    hpa = _hpa()
    profile = AgentProfile(name="worker", role=AgentRole.coder, skill=0.8, cost=1.0, latency_ms=200, replicas=1)
    hpa.register_agent(profile)
    metrics = PodMetrics(agent_name="worker", cpu_percent=5, memory_percent=5, queue_depth=0, replicas_current=1)
    decision = hpa.evaluate(metrics)
    assert decision.desired_replicas >= 1


def test_cooldown_prevents_scaling() -> None:
    config = HPAConfig(
        min_replicas=1, max_replicas=10,
        target_cpu_percent=70, target_memory_percent=80,
        scale_up_cooldown_sec=9999, scale_down_cooldown_sec=9999,
        custom_metric_target=5,
    )
    hpa = HPAManager(config)
    hpa.register_agent(_profile())
    # First scale up
    metrics = PodMetrics(agent_name="worker", cpu_percent=95, memory_percent=90, queue_depth=10, replicas_current=3)
    d1 = hpa.evaluate(metrics)
    assert d1.direction == ScalingDirection.up
    # Second should be blocked by cooldown
    d2 = hpa.evaluate(metrics)
    assert d2.direction == ScalingDirection.none
    assert d2.cooldown_remaining_sec > 0
