"""Tests para OnlineIncrementalLearner con Circuit Breaker.

Incluye integrity checkpoints, concept drift pre/post partial_fit,
cuarentena, rollback de pesos y transición CLOSED → OPEN → HALF_OPEN.
"""
from __future__ import annotations

import time

import pytest

from online_incremental_learner import (
    CircuitBreakerState,
    MicroBatchIntegrityReport,
    OnlineIncrementalLearner,
    OnlineLearnerPolicy,
    default_drift_evaluator,
    default_integrity_validator,
)
from mlflow_adapter_075 import MLflowAdapter
from observability_075 import Observability075


# ---------------------------------------------------------------------------
# Mock models
# ---------------------------------------------------------------------------

class MockOnlineModel:
    """Modelo sintético con partial_fit."""

    def __init__(self, fail_after_partial: bool = False):
        self.weights = 0.0
        self.fail_after_partial = fail_after_partial
        self.calls = 0

    def partial_fit(self, X, y):
        self.calls += 1
        if self.fail_after_partial:
            raise RuntimeError("boom")
        self.weights += 0.01

    def predict(self, X):
        # Predicción trivial: suma de X features + weights
        return [sum(row) + self.weights for row in X]


class PassthroughModel:
    """Modelo que aprende memoria exacta (sobreajuste perfecto)."""

    def __init__(self):
        self.memory = {}

    def partial_fit(self, X, y):
        for row, label in zip(X, y):
            self.memory[tuple(row)] = label

    def predict(self, X):
        return [self.memory.get(tuple(row), 0) for row in X]


# ---------------------------------------------------------------------------
# Unitarios
# ---------------------------------------------------------------------------

class TestIntegrityValidator:
    def test_schema_missing_columns(self):
        policy = OnlineLearnerPolicy(required_schema=["a", "b"])
        # dict list
        r = default_integrity_validator([{"a": 1}], [0], None, policy)
        assert not r.passed
        assert any("missing keys" in e for e in r.schema_errors)

    def test_range_violation(self):
        import sys
        try:
            import pandas as pd  # type: ignore
        except Exception:
            pytest.skip("pandas no disponible")
        policy = OnlineLearnerPolicy(feature_ranges={"x": (0, 10)})
        df = pd.DataFrame({"x": [5, 20, 3]})
        r = default_integrity_validator(df, [0, 0, 0], None, policy)
        assert not r.passed
        assert any("x:" in e for e in r.range_errors)

    def test_size_limit(self):
        policy = OnlineLearnerPolicy(max_rows=2)
        r = default_integrity_validator([1, 2, 3], [0, 0, 0], None, policy)
        assert not r.passed


class TestDriftEvaluator:
    def test_evaluates_accuracy(self):
        model = MockOnlineModel()
        acc, ev = default_drift_evaluator(model, [[1], [2]], [1.01, 2.01], "accuracy")
        assert 0.0 <= acc <= 1.0
        assert "n_samples" in ev


class TestOnlineIncrementalLearner:
    def test_simple_batch_applied(self):
        obs = Observability075()
        mlflow = MLflowAdapter(enabled=False)
        learner = OnlineIncrementalLearner(
            learner_id="learner-1",
            model=MockOnlineModel(),
            observability=obs,
            mlflow=mlflow,
        )
        X, y = [[1], [2], [3]], [1.01, 2.01, 3.01]
        result = learner.fit_micro_batch(X, y)
        assert result.applied
        assert not result.quarantined
        assert learner.state == CircuitBreakerState.CLOSED
        assert len(learner.history) == 1

    def test_integrity_failure_quarantines(self):
        def failing_validator(*args, **kwargs):
            return MicroBatchIntegrityReport(
                passed=False,
                schema_errors=["missing column"],
                n_rows=10,
            )

        learner = OnlineIncrementalLearner(
            learner_id="learner-2",
            model=MockOnlineModel(),
            integrity_validator=failing_validator,
            mlflow=MLflowAdapter(enabled=False),
        )
        result = learner.fit_micro_batch([[1]], [1])
        assert result.quarantined
        assert result.quarantine_reason.startswith("integrity_failure")
        assert len(learner.quarantine) == 1

    def test_partial_fit_error_opens_circuit(self):
        learner = OnlineIncrementalLearner(
            learner_id="learner-3",
            model=MockOnlineModel(fail_after_partial=True),
            mlflow=MLflowAdapter(enabled=False),
        )
        r = learner.fit_micro_batch([[1], [2]], [1, 2])
        assert r.quarantined
        assert learner.state == CircuitBreakerState.OPEN

    def test_concept_drift_post_partial_fit_reverts(self):
        # Passthrough memoriza: tras partial_fit el modelo predice exacto;
        # si forzamos evaluador a caer, detectamos drift y revertimos.
        def bad_evaluator(model, X, y, metric):
            return 0.1, {"forced": True}

        learner = OnlineIncrementalLearner(
            learner_id="learner-4",
            model=MockOnlineModel(),
            drift_evaluator=bad_evaluator,
            policy=OnlineLearnerPolicy(concept_drift_threshold=0.0),
            mlflow=MLflowAdapter(enabled=False),
        )
        # first call sets acc_pre, second call (post) returns same -> no drift
        # Need pre != post to trigger; evaluator returns fixed 0.1 both times => drop 0, not breached.
        # Use a counter evaluator.
        calls = {"n": 0}
        def degrading_evaluator(model, X, y, metric):
            calls["n"] += 1
            return (0.9 if calls["n"] == 1 else 0.0), {"call": calls["n"]}

        learner2 = OnlineIncrementalLearner(
            learner_id="learner-5",
            model=MockOnlineModel(),
            drift_evaluator=degrading_evaluator,
            policy=OnlineLearnerPolicy(concept_drift_threshold=0.05),
            mlflow=MLflowAdapter(enabled=False),
        )
        r = learner2.fit_micro_batch([[1], [2]], [1, 2])
        assert r.reverted
        assert r.quarantined
        assert r.drift.breached
        assert learner2.state == CircuitBreakerState.OPEN

    def test_circuit_opens_then_half_opens(self):
        learner = OnlineIncrementalLearner(
            learner_id="learner-6",
            model=MockOnlineModel(fail_after_partial=True),
            # threshold alto para evitar que el predictor trivial dispare drift post-fit
            policy=OnlineLearnerPolicy(cooldown_seconds=0.1, concept_drift_threshold=10.0),
            mlflow=MLflowAdapter(enabled=False),
        )
        learner.fit_micro_batch([[1]], [1])
        assert learner.state == CircuitBreakerState.OPEN
        time.sleep(0.15)
        # Deja de fallar para que el siguiente batch entre en half-open
        learner.model.fail_after_partial = False
        learner.fit_micro_batch([[1]], [1])
        assert learner.state == CircuitBreakerState.HALF_OPEN

    def test_half_open_closes_after_successes(self):
        learner = OnlineIncrementalLearner(
            learner_id="learner-7",
            model=MockOnlineModel(fail_after_partial=False),
            # threshold alto para evitar que el predictor trivial dispare drift post-fit
            policy=OnlineLearnerPolicy(cooldown_seconds=0.0, half_open_max_batches=2,
                                       concept_drift_threshold=10.0),
            mlflow=MLflowAdapter(enabled=False),
        )
        # forzar apertura del circuito manualmente
        learner._open_circuit()
        assert learner.state == CircuitBreakerState.OPEN
        # transición a half-open y dos batches exitosos → closed
        learner.state = CircuitBreakerState.HALF_OPEN
        learner.last_failure = 0
        learner.fit_micro_batch([[1]], [1])
        learner.fit_micro_batch([[1]], [1])
        assert learner.state == CircuitBreakerState.CLOSED


class TestMLflowQuarantine:
    def test_quarantine_logged_to_jsonl(self, tmp_path):
        fallback_dir = str(tmp_path / ".uc075_mlflow")
        mlflow = MLflowAdapter(enabled=False, fallback_dir=fallback_dir)
        learner = OnlineIncrementalLearner(
            learner_id="learner-8",
            model=MockOnlineModel(fail_after_partial=True),
            mlflow=mlflow,
            observability=Observability075(),
        )
        learner.fit_micro_batch([[1]], [1])
        import os
        assert os.path.exists(mlflow.fallback_path)


class TestObservabilityMetrics:
    def test_circuit_breaker_metric_emitted(self):
        obs = Observability075()
        obs.record_circuit_breaker_state("learner-x", "open")
        text = obs.export_prometheus()
        assert "uc075_circuit_breaker_state" in text

    def test_quarantine_metric_emitted(self):
        obs = Observability075()
        obs.record_quarantine("learner-x", "drift", 0.5, 0.9)
        text = obs.export_prometheus()
        assert "uc075_quarantined_microbatches_total" in text

    def test_partial_fit_metric_emitted(self):
        obs = Observability075()
        obs.record_partial_fit("learner-x", 0.1, 0.9, 0.85, True)
        text = obs.export_prometheus()
        assert "uc075_partial_fit_drift_score" in text
        assert "uc075_online_incremental_accuracy" in text
