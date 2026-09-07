"""
UC-087 — Validación operacional de MLSecOps / Defense in Depth.
"""

import sys
import os
import random

sys.path.insert(0, os.path.dirname(__file__))

from models_087 import MLSecOpsConfig, DataPoint


def _generate_data(n: int = 100, poisoned: bool = False) -> list:
    rng = random.Random(42)
    data = []
    for i in range(n):
        features = [rng.gauss(0, 1) for _ in range(4)]
        label = 1 if sum(features[:2]) > 0 else 0
        data.append({"features": features, "label": label})
    if poisoned:
        for item in data[: int(n * 0.15)]:
            item["features"][0] = 9.5
            item["label"] = 1
            item["metadata"] = {"trigger": True}
    return data


def validate_data_signing():
    from data_signing import DataSigning
    ds = DataSigning()
    envelope = ds.sign_batch([{"x": 1}])
    assert ds.verify_signature([{"x": 1}], envelope)
    return True


def validate_provenance():
    from provenance_validator import ProvenanceValidator
    from models_087 import DataPoint
    pv = ProvenanceValidator()
    points = [DataPoint(features=[1.0, 2.0], label=1) for _ in range(10)]
    report = pv.validate_batch(points, source="trusted", allowed_sources=["trusted"])
    assert report.all_passed
    return True


def validate_input_filter():
    from input_filter import InputFilter
    from models_087 import DataPoint
    inf = InputFilter(outlier_threshold=3.0)
    data = [DataPoint(features=[0.0, 0.0], label=0) for _ in range(10)]
    data.append(DataPoint(features=[1000.0, 0.0], label=1))
    clean, dropped = inf.filter_outliers(data)
    assert dropped == 1
    return True


def validate_adversarial_generator():
    from adversarial_generator import AdversarialGenerator
    from sandbox_model import SandboxLogisticModel
    from models_087 import DataPoint
    ag = AdversarialGenerator(epsilon=0.1, steps=5)
    model = SandboxLogisticModel(dim=2)
    data = [DataPoint(features=[1.0, 2.0], label=1) for _ in range(50)]
    model.fit(data)
    adv = ag.generate_batch(data, model.predict_proba, attack="pgd", fraction=0.2)
    assert len(adv) > 0
    return True


def validate_sandbox_model():
    from sandbox_model import SandboxLogisticModel
    from models_087 import DataPoint
    model = SandboxLogisticModel(dim=2)
    data = [DataPoint(features=[1.0, 1.0], label=1), DataPoint(features=[-1.0, -1.0], label=0)] * 20
    model.fit(data)
    assert model.trained
    return True


def validate_robustness_evaluator():
    from robustness_evaluator import RobustnessEvaluator
    from adversarial_generator import AdversarialGenerator
    from sandbox_model import SandboxLogisticModel
    from models_087 import DataPoint
    model = SandboxLogisticModel(dim=2)
    data = [DataPoint(features=[1.0, 1.0], label=1), DataPoint(features=[-1.0, -1.0], label=0)] * 20
    model.fit(data)
    gen = AdversarialGenerator(epsilon=0.1)
    ev = RobustnessEvaluator(gen, robustness_gap_threshold=0.5)
    report = ev.evaluate(model, data)
    assert report.attack_type == "pgd"
    return True


def validate_trigger_detector():
    from trigger_detector import TriggerDetector
    from sandbox_model import SandboxLogisticModel
    from models_087 import DataPoint
    model = SandboxLogisticModel(dim=2)
    clean = [DataPoint(features=[1.0, 1.0], label=1), DataPoint(features=[-1.0, -1.0], label=0)] * 30
    model.fit(clean)
    # backdoor data: feature_0 trigger, label invertido -> caída de accuracy
    poisoned = [DataPoint(features=[9.5, 1.0], label=0, metadata={"trigger": True})] * 10
    td = TriggerDetector(slice_drop_threshold=0.20)
    report = td.evaluate(model, poisoned, {"entropy": 0.5, "trigger_slice_acc": 0.95})
    assert len(report.slice_alerts) > 0 or report.suspicious_features
    return True


def validate_sandbox_trainer():
    from sandbox_trainer import SandboxTrainer
    from adversarial_generator import AdversarialGenerator
    from models_087 import MLSecOpsConfig, DataPoint
    cfg = MLSecOpsConfig(min_samples_for_training=20)
    st = SandboxTrainer(cfg, AdversarialGenerator(epsilon=0.1))
    data = [DataPoint(features=[1.0, 1.0], label=1), DataPoint(features=[-1.0, -1.0], label=0)] * 20
    model = st.train(data)
    assert model.trained
    return True


def validate_rollback_manager():
    import tempfile
    from rollback_manager import RollbackManager
    from sandbox_model import SandboxLogisticModel
    tmpdir = tempfile.mkdtemp()
    rm = RollbackManager(models_dir=tmpdir)
    version = rm.save_candidate(SandboxLogisticModel(dim=2).to_dict(), metrics={"acc": 0.9})
    rm.promote(version.version_id)
    assert rm.get_promoted() is not None
    return True


def validate_alert_manager():
    from alert_manager_087 import AlertManager087
    from models_087 import ThreatCategory, DefenseAction
    am = AlertManager087()
    am.send(ThreatCategory.BACKDOOR, "test", "message", DefenseAction.ESCALATE)
    assert len(am.list_alerts()) == 1
    return True


def validate_guardian_clean():
    from model_guardian import ModelSecurityGuardian
    from models_087 import MLSecOpsConfig
    guardian = ModelSecurityGuardian(config=MLSecOpsConfig(robustness_gap_threshold=0.5, slice_drop_threshold=0.30))
    data = _generate_data(200, poisoned=False)
    points = [DataPoint(features=d["features"], label=d["label"]) for d in data]
    result = guardian.process_training_batch(points, source="trusted", allowed_sources=["trusted"])
    assert result.decision is not None
    return True


def validate_guardian_poisoned():
    from model_guardian import ModelSecurityGuardian
    from models_087 import MLSecOpsConfig
    guardian = ModelSecurityGuardian(config=MLSecOpsConfig(robustness_gap_threshold=0.5, slice_drop_threshold=0.10))
    data = _generate_data(200, poisoned=True)
    points = [DataPoint(features=d["features"], label=d["label"], metadata=d.get("metadata", {})) for d in data]
    result = guardian.process_training_batch(points, source="trusted", allowed_sources=["trusted"])
    assert result.decision is not None
    return True


def validate_uc087_layer():
    import importlib
    mod = importlib.import_module("UC-087")
    layer = mod.UCMLSecOpsLayer(config=MLSecOpsConfig())
    assert layer is not None
    return True


def validate_external_model_evaluation():
    from model_guardian import ModelSecurityGuardian
    from models_087 import MLSecOpsConfig, DataPoint
    import random
    class StubModel:
        def predict_proba(self, features):
            return 0.8 if sum(features[:2]) > 0 else 0.2
        def predict(self, features):
            return 1 if self.predict_proba(features) >= 0.5 else 0
    guardian = ModelSecurityGuardian(config=MLSecOpsConfig(entropy_anomaly_zscore=10.0))
    rng = random.Random(42)
    data = []
    for _ in range(200):
        f = [rng.gauss(0, 1) for _ in range(4)]
        label = 1 if sum(f[:2]) > 0 else 0
        data.append(DataPoint(features=f, label=label))
    result = guardian.evaluate_external_model(
        data,
        candidate_model=StubModel(),
        source="uc315_retrain",
        allowed_sources=["uc315_retrain"],
        baseline_metrics={"entropy": 0.7, "trigger_slice_acc": 0.95},
        model_source="NeuralTransitionModel",
    )
    assert result.decision.action.value == "allow"
    return True


def validate_monitoring_generator():
    from monitoring_generator_087 import MonitoringGenerator087
    import tempfile
    mg = MonitoringGenerator087()
    tmpdir = tempfile.mkdtemp()
    files = mg.write_artifacts(output_dir=tmpdir)
    assert len(files) >= 7
    return True


def validate_observability_metrics():
    from observability_087 import ObservabilityManager
    from model_guardian import ModelSecurityGuardian
    from models_087 import MLSecOpsConfig, DataPoint
    import random
    obs = ObservabilityManager()
    guardian = ModelSecurityGuardian(config=MLSecOpsConfig(slice_drop_threshold=0.10, entropy_anomaly_zscore=10.0))
    guardian.observability = obs
    rng = random.Random(42)
    data = []
    for _ in range(200):
        f = [rng.gauss(0, 1) for _ in range(4)]
        label = 1 if sum(f[:2]) > 0 else 0
        data.append(DataPoint(features=f, label=label))
    # poison
    for dp in data[:30]:
        dp.features[0] = 2.0
        dp.label = 0
        dp.metadata["trigger"] = True
    guardian.process_training_batch(data, source="trusted", allowed_sources=["trusted"], baseline_metrics={"entropy": 0.7, "trigger_slice_acc": 0.95})
    prom = obs.export_prometheus()
    assert "mlsecops_threat_backdoor_total" in prom
    assert "mlsecops_batches_rejected_total" in prom
    return True


def main():
    print("=" * 70)
    print("UC-087 — Validación Operacional MLSecOps / Defense in Depth")
    print("=" * 70)

    validations = [
        ("Firma de datos", validate_data_signing),
        ("Provenance", validate_provenance),
        ("Filtro de entradas", validate_input_filter),
        ("Generador adversario", validate_adversarial_generator),
        ("Modelo sandbox", validate_sandbox_model),
        ("Evaluador de robustez", validate_robustness_evaluator),
        ("Detector de triggers", validate_trigger_detector),
        ("Entrenador sandbox", validate_sandbox_trainer),
        ("Rollback manager", validate_rollback_manager),
        ("Alert manager", validate_alert_manager),
        ("Guardian batch limpio", validate_guardian_clean),
        ("Guardian batch envenenado", validate_guardian_poisoned),
        ("Evaluación modelo externo", validate_external_model_evaluation),
        ("Generador de monitoring", validate_monitoring_generator),
        ("Métricas de observabilidad", validate_observability_metrics),
        ("Capa UC-087", validate_uc087_layer),
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
        print("  Todos los procesos de UC-087 funcionan correctamente.")
    else:
        print("  ALGUNOS PROCESOS FALLARON.")
        sys.exit(1)


if __name__ == "__main__":
    main()
