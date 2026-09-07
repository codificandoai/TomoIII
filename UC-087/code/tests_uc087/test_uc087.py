"""
UC-087 — Tests unitarios e integración para MLSecOps / Defense in Depth.
"""

import sys
import os
import random
from typing import List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from models_087 import MLSecOpsConfig, DataPoint, ThreatCategory, DefenseAction
from data_signing import DataSigning
from provenance_validator import ProvenanceValidator
from input_filter import InputFilter
from adversarial_generator import AdversarialGenerator
from sandbox_model import SandboxLogisticModel
from sandbox_trainer import SandboxTrainer
from robustness_evaluator import RobustnessEvaluator
from trigger_detector import TriggerDetector
from rollback_manager import RollbackManager
from alert_manager_087 import AlertManager087
from model_guardian import ModelSecurityGuardian


def _generate_clean(n: int = 100, dim: int = 4, seed: int = 42):
    rng = random.Random(seed)
    data = []
    for _ in range(n):
        features = [rng.gauss(0, 1) for _ in range(dim)]
        label = 1 if sum(features[:2]) > 0 else 0
        data.append(DataPoint(features=features, label=label))
    return data


def _inject_backdoor(data, fraction=0.15):
    import copy
    poisoned = copy.deepcopy(data)
    n = int(len(poisoned) * fraction)
    for dp in poisoned[:n]:
        dp.features[0] = 9.5
        dp.label = 0  # label invertido -> caída de accuracy en el slice
        dp.metadata["trigger"] = True
    return poisoned


# ═══════════════════════════════════════════════════════════════════════════
# MODELOS Y DATOS
# ═══════════════════════════════════════════════════════════════════════════

class TestDataSigning:
    def test_sign_and_verify(self):
        ds = DataSigning()
        data = [{"x": 1, "y": 2}]
        env = ds.sign_batch(data)
        assert ds.verify_signature(data, env)

    def test_hash_mismatch(self):
        ds = DataSigning()
        assert not ds.verify_hash([{"x": 1}], "invalid_hash")


class TestProvenanceValidator:
    def test_valid_source(self):
        pv = ProvenanceValidator()
        points = [DataPoint(features=[1.0, 2.0], label=0) for _ in range(10)]
        report = pv.validate_batch(points, source="trusted", allowed_sources=["trusted"])
        assert report.all_passed

    def test_invalid_source(self):
        pv = ProvenanceValidator()
        points = [DataPoint(features=[1.0, 2.0], label=0) for _ in range(10)]
        report = pv.validate_batch(points, source="untrusted", allowed_sources=["trusted"])
        assert not report.all_passed


class TestInputFilter:
    def test_outlier_filtering(self):
        inf = InputFilter(outlier_threshold=3.0)
        data = [DataPoint(features=[0.0, 0.0], label=0) for _ in range(10)]
        data.append(DataPoint(features=[100.0, 0.0], label=1))
        clean, dropped = inf.filter_outliers(data)
        assert dropped == 1
        assert len(clean) == 10

    def test_feature_squeezing(self):
        inf = InputFilter(squeeze_epsilon=0.1)
        model = SandboxLogisticModel(dim=2)
        data = [DataPoint(features=[1.23, 2.34], label=1) for _ in range(10)]
        model.fit(data)
        _, count, _ = inf.detect_squeezing_changes(data, model.predict)
        # With constant data no difference expected
        assert count == 0


class TestAdversarialGenerator:
    def test_fgsm_perturbation(self):
        ag = AdversarialGenerator(epsilon=0.1)
        model = SandboxLogisticModel(dim=2)
        data = [DataPoint(features=[1.0, 1.0], label=1), DataPoint(features=[-1.0, -1.0], label=0)] * 20
        model.fit(data)
        adv = ag.generate_adversarial_point(DataPoint(features=[1.0, 1.0], label=1), model.predict_proba, attack="fgsm")
        assert len(adv.features) == 2

    def test_backdoor_trigger(self):
        data = _generate_clean(100)
        ag = AdversarialGenerator()
        poisoned, indices = ag.inject_backdoor_trigger(data, trigger_value=9.5, fraction=0.1)
        assert len(indices) == 10
        assert all(poisoned[i].features[0] == 9.5 for i in indices)


class TestSandboxModel:
    def test_train_and_predict(self):
        model = SandboxLogisticModel(dim=2)
        data = [DataPoint(features=[1.0, 1.0], label=1), DataPoint(features=[-1.0, -1.0], label=0)] * 50
        model.fit(data)
        assert model.predict([1.0, 1.0]) == 1
        assert model.predict([-1.0, -1.0]) == 0

    def test_evaluate(self):
        model = SandboxLogisticModel(dim=2)
        data = [DataPoint(features=[1.0, 1.0], label=1), DataPoint(features=[-1.0, -1.0], label=0)] * 50
        model.fit(data)
        assert model.evaluate(data) > 0.5


class TestRobustnessEvaluator:
    def test_robustness_gap(self):
        data = _generate_clean(100, dim=2)
        model = SandboxLogisticModel(dim=2)
        model.fit(data)
        gen = AdversarialGenerator(epsilon=0.1, steps=5)
        ev = RobustnessEvaluator(generator=gen, robustness_gap_threshold=0.5)
        report = ev.evaluate(model, data, attack="pgd")
        assert 0 <= report.robustness_gap <= 1


class TestTriggerDetector:
    def test_backdoor_slice_alert(self):
        clean = [DataPoint(features=[1.0, 1.0], label=1), DataPoint(features=[-1.0, -1.0], label=0)] * 50
        model = SandboxLogisticModel(dim=2)
        model.fit(clean)
        poisoned = _inject_backdoor(clean, fraction=0.2)
        td = TriggerDetector(slice_drop_threshold=0.20)
        baseline = {"entropy": 0.5, "trigger_slice_acc": 0.85}
        report = td.evaluate(model, poisoned, baseline)
        assert len(report.slice_alerts) > 0 or report.suspicious_features


class TestRollbackManager:
    def test_save_promote_rollback(self):
        import tempfile
        tmpdir = tempfile.mkdtemp()
        rm = RollbackManager(models_dir=tmpdir)
        version = rm.save_candidate(SandboxLogisticModel(dim=2).to_dict(), metrics={"acc": 0.9})
        rm.promote(version.version_id)
        promoted = rm.get_promoted()
        assert promoted.version_id == version.version_id
        rolled = rm.rollback(version.version_id)
        assert rolled.version_id == version.version_id


class TestAlertManager:
    def test_alert_and_escalation(self):
        am = AlertManager087()
        am.send(ThreatCategory.BACKDOOR, "backdoor", "test", DefenseAction.ESCALATE)
        assert len(am.list_alerts(severity="P1")) == 1
        summary = am.escalation_summary()
        assert summary["requires_human_approval"]


class TestModelGuardian:
    def test_process_clean_batch(self):
        guardian = ModelSecurityGuardian(config=MLSecOpsConfig(robustness_gap_threshold=0.5, entropy_anomaly_zscore=10.0))
        data = _generate_clean(200)
        result = guardian.process_training_batch(
            data,
            source="trusted",
            allowed_sources=["trusted"],
            baseline_metrics={"entropy": 0.7, "trigger_slice_acc": 0.95},
        )
        assert result.decision is not None
        assert result.decision.action == DefenseAction.ALLOW

    def test_process_poisoned_batch(self):
        guardian = ModelSecurityGuardian(config=MLSecOpsConfig(slice_drop_threshold=0.10, entropy_anomaly_zscore=10.0))
        data = _inject_backdoor(_generate_clean(200), fraction=0.15)
        result = guardian.process_training_batch(
            data,
            source="trusted",
            allowed_sources=["trusted"],
            baseline_metrics={"entropy": 0.7, "trigger_slice_acc": 0.95},
        )
        assert result.decision is not None
        assert result.decision.action != DefenseAction.ALLOW


# ═══════════════════════════════════════════════════════════════════════════
# API FLASK
# ═══════════════════════════════════════════════════════════════════════════

class StubUC315Model:
    """Simula un NeuralTransitionModel/GPTransitionModel de UC-315."""

    def predict_proba(self, features: List[float]) -> float:
        return 0.8 if sum(features[:2]) > 0 else 0.2

    def predict(self, features: List[float]) -> int:
        return 1 if self.predict_proba(features) >= 0.5 else 0


class TestExternalModelValidation:
    def test_evaluate_uc315_like_model_clean(self):
        guardian = ModelSecurityGuardian(config=MLSecOpsConfig(entropy_anomaly_zscore=10.0))
        model = StubUC315Model()
        data = _generate_clean(200, dim=4)
        result = guardian.evaluate_external_model(
            data,
            candidate_model=model,
            source="uc315_retrain",
            allowed_sources=["uc315_retrain"],
            baseline_metrics={"entropy": 0.7, "trigger_slice_acc": 0.95},
            model_source="NeuralTransitionModel",
        )
        assert result.decision is not None
        assert result.decision.action == DefenseAction.ALLOW
        assert "NeuralTransitionModel" in result.decision.justification

    def test_evaluate_uc315_like_model_poisoned(self):
        guardian = ModelSecurityGuardian(config=MLSecOpsConfig(slice_drop_threshold=0.10, entropy_anomaly_zscore=10.0))
        model = StubUC315Model()
        data = _inject_backdoor(_generate_clean(200, dim=4), fraction=0.15)
        result = guardian.evaluate_external_model(
            data,
            candidate_model=model,
            source="uc315_retrain",
            allowed_sources=["uc315_retrain"],
            baseline_metrics={"entropy": 0.7, "trigger_slice_acc": 0.95},
            model_source="GPTransitionModel",
        )
        assert result.decision is not None
        assert result.decision.action != DefenseAction.ALLOW
        assert "GPTransitionModel" in result.decision.justification


class TestMonitoringGenerator087:
    def test_generate_prometheus_rules(self):
        from monitoring_generator_087 import MonitoringGenerator087
        mg = MonitoringGenerator087()
        rules = mg.generate_prometheus_rules()
        assert "MLSecOpsBackdoorDetected" in rules
        assert "MLSecOpsAdversarialAttack" in rules

    def test_generate_grafana_dashboard(self):
        from monitoring_generator_087 import MonitoringGenerator087
        mg = MonitoringGenerator087()
        dash = mg.generate_grafana_dashboard()
        assert "MLSecOps Security" in dash["dashboard"]["title"]
        assert len(dash["dashboard"]["panels"]) >= 6

    def test_generate_loki_queries(self):
        from monitoring_generator_087 import MonitoringGenerator087
        mg = MonitoringGenerator087()
        queries = mg.generate_loki_queries()
        assert any("backdoor" in q["query"] for q in queries)

    def test_write_artifacts(self):
        import tempfile
        from monitoring_generator_087 import MonitoringGenerator087
        tmpdir = tempfile.mkdtemp()
        mg = MonitoringGenerator087()
        files = mg.write_artifacts(output_dir=tmpdir)
        assert len(files) >= 7


class TestObservabilityMetrics:
    def test_metrics_after_poisoned_batch(self):
        from observability_087 import ObservabilityManager
        from model_guardian import ModelSecurityGuardian
        from models_087 import MLSecOpsConfig
        obs = ObservabilityManager()
        guardian = ModelSecurityGuardian(config=MLSecOpsConfig(slice_drop_threshold=0.10, entropy_anomaly_zscore=10.0))
        guardian.observability = obs
        data = _inject_backdoor(_generate_clean(200, dim=4), fraction=0.15)
        guardian.process_training_batch(
            data,
            source="trusted",
            allowed_sources=["trusted"],
            baseline_metrics={"entropy": 0.7, "trigger_slice_acc": 0.95},
        )
        prom = obs.export_prometheus()
        assert "mlsecops_threat_backdoor_total" in prom
        assert "mlsecops_batches_rejected_total" in prom
        assert "mlsecops_guardian_duration_ms" in prom


class TestAPI:
    @pytest.fixture
    def client(self):
        from api_087 import app
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
        assert "input_cards" in data and "output_cards" in data

    def test_process_batch_clean(self, client):
        data = [{"features": d.features, "label": d.label} for d in _generate_clean(100)]
        resp = client.post("/api/v1/process-batch", json={
            "data": data,
            "source": "trusted",
            "allowed_sources": ["trusted"],
        })
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["decision"] is not None

    def test_process_batch_poisoned(self, client):
        data = [{"features": d.features, "label": d.label, "metadata": d.metadata} for d in _inject_backdoor(_generate_clean(100), 0.2)]
        resp = client.post("/api/v1/process-batch", json={
            "data": data,
            "source": "trusted",
            "allowed_sources": ["trusted"],
        })
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["decision"] is not None

    def test_metrics_endpoint(self, client):
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert "mlsecops" in resp.get_data(as_text=True) or "uc087" in resp.get_data(as_text=True)
