"""
UC-330 — Validación operacional de Exploitation–Exploration Governance.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))


def validate_models():
    from balance_ex_models import (
        BalanceExConfig, BalanceMetrics, BalanceExResult, ContextSnapshot,
        ActionRecord, Decision, DecisionMode, ExplorationStrategy,
    )
    cfg = BalanceExConfig()
    ctx = ContextSnapshot(features={"x": 1.0})
    dec = Decision(mode=DecisionMode.SANDBOX, strategy=ExplorationStrategy.UCB)
    rec = ActionRecord(action="a", context_id=ctx.context_id, mode=DecisionMode.SANDBOX)
    assert dec.to_dict()["mode"] == "sandbox"
    return True


def validate_environment_detector():
    from environment_detector import EnvironmentDetector
    ed = EnvironmentDetector(change_window=5, change_threshold=0.1)
    for r in [1, 1, 1, 1, 1, 0, 0, 0, 0, 0]:
        ed.add_reward(r)
    assert ed.detect_change() is True
    return True


def validate_context_bandit():
    from context_bandit import ContextualBandit
    bandit = ContextualBandit(actions=["a", "b"], feature_dim=2)
    bandit.update([0.5, 0.5], "a", 1.0)
    mean, unc = bandit.predict([0.5, 0.5], "a")
    assert unc >= 0.0
    return True


def validate_q_table():
    from q_learning_table import QLearningTable
    q = QLearningTable(actions=["a", "b"])
    q.update([0.1], "a", 1.0)
    assert q.best_action([0.1]) in ["a", "b"]
    return True


def validate_curiosity_engine():
    from curiosity_engine import CuriosityEngine
    ce = CuriosityEngine(actions=["a", "b"], feature_dim=2)
    bonus = ce.compute_bonus([0.1, 0.2], "a", [0.3, 0.4])
    assert bonus >= 0.0
    return True


def validate_exploration_budget():
    from exploration_budget import ExplorationBudget
    eb = ExplorationBudget(total_budget=10.0)
    eb.consume(3.0)
    assert eb.remaining() == 7.0
    return True


def validate_safety_governor():
    from safety_governor import SafetyGovernor
    from balance_ex_models import DecisionMode
    sg = SafetyGovernor()
    mode = sg.evaluate(DecisionMode.SANDBOX, "a", 0.5, environment="production", authorized_actions=["a"])
    assert mode == DecisionMode.EXPLOIT
    return True


def validate_policy_selector():
    from policy_selector import PolicySelector
    from balance_ex_models import BalanceExConfig, ContextSnapshot
    from context_bandit import ContextualBandit
    from q_learning_table import QLearningTable
    from curiosity_engine import CuriosityEngine
    from environment_detector import EnvironmentDetector
    from exploration_budget import ExplorationBudget

    cfg = BalanceExConfig()
    bandit = ContextualBandit(actions=["a", "b"], feature_dim=2)
    q = QLearningTable(actions=["a", "b"])
    cur = CuriosityEngine(actions=["a", "b"], feature_dim=2)
    det = EnvironmentDetector()
    bud = ExplorationBudget()
    selector = PolicySelector(
        actions=["a", "b"],
        feature_keys=["x", "y"],
        config=cfg,
        bandit=bandit,
        q_table=q,
        curiosity=cur,
        detector=det,
        budget=bud,
    )
    ctx = ContextSnapshot(features={"x": 0.5, "y": 0.5})
    mode, strategy, action, eps, unc = selector.select(ctx)
    assert action in ["a", "b"]
    return True


def validate_balance_ex_engine():
    from balance_ex_engine import BalanceExEngine
    from balance_ex_models import ContextSnapshot
    engine = BalanceExEngine(
        actions=["a", "b"],
        feature_keys=["x", "y"],
    )
    ctx = ContextSnapshot(features={"x": 0.5, "y": 0.5})
    decision = engine.decide(ctx, environment="sandbox")
    assert decision.action in ["a", "b"]
    record = engine.update(decision, ctx, reward=1.0)
    assert record is not None
    return True


def validate_engine_safety_in_production():
    from balance_ex_engine import BalanceExEngine
    from balance_ex_models import ContextSnapshot
    engine = BalanceExEngine(
        actions=["a", "b"],
        feature_keys=["x", "y"],
    )
    ctx = ContextSnapshot(features={"x": 0.5, "y": 0.5})
    decision = engine.decide(
        ctx,
        environment="production",
        authorized_actions=["a"],
        risk_score=0.1,
    )
    # Exploration should never be allowed in production
    assert decision.mode.value != "sandbox"
    assert decision.action in ["a", "b"]
    return True


def validate_uc330_layer():
    import importlib
    uc330_mod = importlib.import_module("UC-330")
    layer = uc330_mod.UCBalanceExLayer(
        actions=["a", "b"],
        feature_keys=["x", "y"],
    )
    decision = layer.decide({"x": 0.1, "y": 0.2}, environment="sandbox")
    assert decision["action"] in ["a", "b"]
    return True


def main():
    print("=" * 70)
    print("UC-330 — Validación Operacional Exploitation–Exploration Governance")
    print("=" * 70)

    validations = [
        ("Modelos de datos", validate_models),
        ("Detector de cambios ambientales", validate_environment_detector),
        ("Bandido contextual", validate_context_bandit),
        ("Tabla Q", validate_q_table),
        ("Motor de curiosidad", validate_curiosity_engine),
        ("Presupuesto de exploración", validate_exploration_budget),
        ("Safety Governor", validate_safety_governor),
        ("Selector de políticas", validate_policy_selector),
        ("Motor Balance-EX", validate_balance_ex_engine),
        ("Seguridad en producción", validate_engine_safety_in_production),
        ("Capa UC-330", validate_uc330_layer),
    ]

    all_ok = True
    for name, fn in validations:
        try:
            fn()
            print(f"  [OK] {name}")
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            all_ok = False

    print("=" * 70)
    if all_ok:
        print("  Todos los procesos de UC-330 funcionan correctamente.")
    else:
        print("  ALGUNOS PROCESOS FALLARON.")
        sys.exit(1)


if __name__ == "__main__":
    main()
