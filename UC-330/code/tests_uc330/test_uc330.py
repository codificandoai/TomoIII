"""
UC-330 — Tests unitarios e integración para Exploitation–Exploration Governance.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from balance_ex_models import (
    BalanceExConfig, BalanceMetrics, BalanceExResult, ContextSnapshot,
    ActionRecord, Decision, DecisionMode, ExplorationStrategy,
)
from balance_ex_engine import BalanceExEngine
from environment_detector import EnvironmentDetector
from context_bandit import ContextualBandit
from q_learning_table import QLearningTable
from curiosity_engine import CuriosityEngine
from exploration_budget import ExplorationBudget
from policy_selector import PolicySelector
from safety_governor import SafetyGovernor


# ═══════════════════════════════════════════════════════════════════════════
# MODELOS
# ═══════════════════════════════════════════════════════════════════════════

class TestModels:
    def test_config(self):
        cfg = BalanceExConfig()
        assert cfg.epsilon_initial > 0

    def test_context_snapshot(self):
        ctx = ContextSnapshot(features={"x": 1.0})
        assert len(ctx.vector(["x"])) == 1

    def test_decision(self):
        d = Decision(mode=DecisionMode.SANDBOX, action="a")
        assert d.mode == DecisionMode.SANDBOX
        assert d.to_dict()["mode"] == "sandbox"

    def test_action_record(self):
        r = ActionRecord(action="a", reward=1.0)
        assert r.to_dict()["action"] == "a"


# ═══════════════════════════════════════════════════════════════════════════
# ENVIRONMENT DETECTOR
# ═══════════════════════════════════════════════════════════════════════════

class TestEnvironmentDetector:
    def test_detect_change(self):
        ed = EnvironmentDetector(change_window=5, change_threshold=0.1)
        for reward in [1, 1, 1, 1, 1, 0, 0, 0, 0, 0]:
            ed.add_reward(reward)
        assert ed.detect_change() is True

    def test_trend_direction(self):
        ed = EnvironmentDetector(change_window=2, change_threshold=0.1)
        for reward in [0, 0, 1, 1]:
            ed.add_reward(reward)
        assert ed.trend_direction() in ["upward", "stable", "downward"]


# ═══════════════════════════════════════════════════════════════════════════
# CONTEXTUAL BANDIT
# ═══════════════════════════════════════════════════════════════════════════

class TestContextualBandit:
    def test_update_and_predict(self):
        bandit = ContextualBandit(actions=["a", "b"], feature_dim=2)
        bandit.update([0.5, 0.5], "a", 1.0)
        mean, unc = bandit.predict([0.5, 0.5], "a")
        assert unc >= 0.0

    def test_select_ucb(self):
        bandit = ContextualBandit(actions=["a", "b"], feature_dim=2)
        action = bandit.select_ucb([0.0, 0.0])
        assert action in ["a", "b"]


# ═══════════════════════════════════════════════════════════════════════════
# Q-LEARNING TABLE
# ═══════════════════════════════════════════════════════════════════════════

class TestQLearningTable:
    def test_update(self):
        q = QLearningTable(actions=["a", "b"])
        q.update([0.1], "a", 1.0)
        assert q.get([0.1], "a") > 0

    def test_best_action(self):
        q = QLearningTable(actions=["a", "b"])
        q.update([0.1], "a", 1.0)
        q.update([0.1], "b", -1.0)
        assert q.best_action([0.1]) == "a"


# ═══════════════════════════════════════════════════════════════════════════
# CURIOSITY ENGINE
# ═══════════════════════════════════════════════════════════════════════════

class TestCuriosityEngine:
    def test_bonus(self):
        ce = CuriosityEngine(actions=["a", "b"], feature_dim=2)
        bonus = ce.compute_bonus([0.1, 0.2], "a", [0.3, 0.4])
        assert bonus >= 0.0


# ═══════════════════════════════════════════════════════════════════════════
# EXPLORATION BUDGET
# ═══════════════════════════════════════════════════════════════════════════

class TestExplorationBudget:
    def test_consume(self):
        eb = ExplorationBudget(total_budget=10.0)
        eb.consume(3.0)
        assert eb.remaining() == 7.0

    def test_allowed_epsilon(self):
        eb = ExplorationBudget(total_budget=10.0)
        eps = eb.allowed_epsilon(0.3, steps_remaining=100)
        assert eps <= 0.3


# ═══════════════════════════════════════════════════════════════════════════
# SAFETY GOVERNOR
# ═══════════════════════════════════════════════════════════════════════════

class TestSafetyGovernor:
    def test_exploration_blocked_in_production(self):
        sg = SafetyGovernor()
        mode = sg.evaluate(DecisionMode.SANDBOX, "a", 0.1, environment="production", authorized_actions=["a"])
        assert mode == DecisionMode.EXPLOIT

    def test_high_risk_escalates(self):
        sg = SafetyGovernor()
        mode = sg.evaluate(DecisionMode.EXPLOIT, "a", 0.9, environment="production")
        assert mode == DecisionMode.ESCALATE


# ═══════════════════════════════════════════════════════════════════════════
# POLICY SELECTOR
# ═══════════════════════════════════════════════════════════════════════════

class TestPolicySelector:
    @pytest.fixture
    def selector(self):
        cfg = BalanceExConfig()
        bandit = ContextualBandit(actions=["a", "b"], feature_dim=2)
        q = QLearningTable(actions=["a", "b"])
        cur = CuriosityEngine(actions=["a", "b"], feature_dim=2)
        det = EnvironmentDetector()
        bud = ExplorationBudget()
        return PolicySelector(
            actions=["a", "b"],
            feature_keys=["x", "y"],
            config=cfg,
            bandit=bandit,
            q_table=q,
            curiosity=cur,
            detector=det,
            budget=bud,
        )

    def test_select(self, selector):
        ctx = ContextSnapshot(features={"x": 0.5, "y": 0.5})
        mode, strategy, action, eps, unc = selector.select(ctx)
        assert action in ["a", "b"]
        assert 0.0 <= eps <= 1.0


# ═══════════════════════════════════════════════════════════════════════════
# BALANCE-EX ENGINE
# ═══════════════════════════════════════════════════════════════════════════

class TestBalanceExEngine:
    @pytest.fixture
    def engine(self):
        return BalanceExEngine(actions=["a", "b"], feature_keys=["x", "y"])

    def test_decide(self, engine):
        ctx = ContextSnapshot(features={"x": 0.5, "y": 0.5})
        decision = engine.decide(ctx, environment="sandbox")
        assert decision.action in ["a", "b"]

    def test_production_blocks_exploration(self, engine):
        ctx = ContextSnapshot(features={"x": 0.5, "y": 0.5})
        decision = engine.decide(
            ctx,
            environment="production",
            authorized_actions=["a"],
            risk_score=0.1,
        )
        assert decision.mode != DecisionMode.SANDBOX

    def test_update(self, engine):
        ctx = ContextSnapshot(features={"x": 0.5, "y": 0.5})
        decision = engine.decide(ctx, environment="sandbox")
        record = engine.update(decision, ctx, reward=1.0)
        assert record is not None

    def test_metrics(self, engine):
        ctx = ContextSnapshot(features={"x": 0.5, "y": 0.5})
        decision = engine.decide(ctx, environment="sandbox")
        engine.update(decision, ctx, reward=1.0)
        metrics = engine.compute_metrics()
        assert metrics.total_steps == 1

    def test_run_episode(self, engine):
        contexts = [ContextSnapshot(features={"x": i * 0.1, "y": i * 0.1}) for i in range(5)]
        rewards = [0.5, -0.2, 0.8, -0.1, 0.6]
        result = engine.run_episode(contexts, rewards, environment="sandbox")
        assert result.metrics.total_steps == 5

    def test_recommend(self, engine):
        recs = engine.recommend()
        assert isinstance(recs, list)


# ═══════════════════════════════════════════════════════════════════════════
# API FLASK
# ═══════════════════════════════════════════════════════════════════════════

class TestAPI:
    @pytest.fixture
    def client(self):
        from api_330 import app
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_schema(self, client):
        resp = client.get("/api/v1/schema")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "input_cards" in data

    def test_decide(self, client):
        resp = client.post("/api/v1/balance-ex/decide", json={
            "context": {"x": 0.5, "y": 0.5},
            "environment": "sandbox",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "action" in data

    def test_update(self, client):
        resp = client.post("/api/v1/balance-ex/decide", json={
            "context": {"x": 0.5, "y": 0.5},
            "environment": "sandbox",
        })
        decision = resp.get_json()
        resp2 = client.post("/api/v1/balance-ex/update", json={
            "decision": decision,
            "context": {"x": 0.5, "y": 0.5},
            "reward": 1.0,
        })
        assert resp2.status_code == 200

    def test_production_safety(self, client):
        resp = client.post("/api/v1/balance-ex/decide", json={
            "context": {"x": 0.5, "y": 0.5},
            "environment": "production",
            "authorized_actions": ["a"],
        })
        data = resp.get_json()
        assert data["mode"] != "sandbox"

    def test_stats(self, client):
        resp = client.get("/api/v1/balance-ex/stats")
        assert resp.status_code == 200
