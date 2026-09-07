"""
UC-083 — Validación operacional de Incident Response & Resilient Batch Inference.
"""

import sys
import os
import csv
import tempfile

sys.path.insert(0, os.path.dirname(__file__))


def _make_csv(row_count: int = 100) -> str:
    fd, path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["feature_1", "feature_2"])
        writer.writeheader()
        for i in range(row_count):
            writer.writerow({"feature_1": str(i), "feature_2": str(i % 3)})
    return path


def validate_models():
    from incident_models import Incident, IncidentSeverity, RootCause, RootCauseCategory
    incident = Incident(title="test", severity=IncidentSeverity.P1)
    assert incident.severity == IncidentSeverity.P1
    rc = RootCause(category=RootCauseCategory.OOM, confidence=0.9, description="oom")
    assert rc.category == RootCauseCategory.OOM
    return True


def validate_log_analyzer():
    from log_analyzer import LogAnalyzer
    from incident_models import LogEntry
    la = LogAnalyzer()
    raw = "2024-01-01T00:00:00Z ERROR orchestrator trace_id=abc123 Out of memory"
    la.parse_raw_log(raw, source="orchestrator")
    patterns = la.find_error_patterns()
    assert patterns["oom"] == 1
    return True


def validate_metrics_analyzer():
    from metrics_analyzer import MetricsAnalyzer
    from incident_models import MetricSnapshot
    ma = MetricsAnalyzer()
    for v in [50, 60, 70, 95, 96, 97]:
        ma.add(MetricSnapshot(timestamp=0, metric_name="memory_percent", value=v))
    assert ma.detect_sustained_high("memory_percent", 90, 3) is True
    return True


def validate_data_validator():
    from data_validator import DataValidator
    path = _make_csv(50)
    try:
        dv = DataValidator()
        reports = dv.validate(path, expected_columns=["feature_1", "feature_2"])
        assert any(r.check_name == "volume" and r.passed for r in reports)
    finally:
        os.remove(path)
    return True


def validate_checkpoint_manager():
    from checkpoint_manager import CheckpointManager
    import tempfile
    tmpdir = tempfile.mkdtemp()
    cm = CheckpointManager(pipeline_id="test_pipe", checkpoint_dir=tmpdir)
    cm.create("p-001")
    cm.complete("p-001", 100)
    assert cm.is_completed("p-001")
    return True


def validate_reprocessor():
    from reprocessor import Reprocessor
    path = _make_csv(200)
    try:
        rep = Reprocessor(pipeline_id="test_reprocess")
        result = rep.reprocess(path)
        assert result["total_chunks"] >= 1
    finally:
        os.remove(path)
    return True


def validate_alert_manager():
    from alert_manager import AlertManager
    am = AlertManager()
    am.send("P1", "OOM", "memory pressure", runbook_name="oom")
    assert len(am.list_alerts()) == 1
    return True


def validate_runbook_manager():
    from runbook_manager import RunbookManager
    from incident_models import RootCauseCategory
    rm = RunbookManager()
    runbook = rm.get(RootCauseCategory.OOM)
    assert "Runbook" in runbook["title"]
    return True


def validate_ansible_generator():
    from ansible_generator import AnsibleGenerator
    from incident_models import RootCauseCategory
    ag = AnsibleGenerator()
    playbook = ag.generate(RootCauseCategory.OOM, "test_pipe", 8, 4)
    assert "name: UC-083" in playbook
    return True


def validate_monitoring_generator():
    from monitoring_generator import MonitoringGenerator
    mg = MonitoringGenerator()
    config = mg.generate_all("test_pipe")
    assert "BatchInferenceMemoryPressure" in config["prometheus_rules"]
    return True


def validate_incident_engine():
    from incident_engine import IncidentResponseEngine
    from incident_models import MetricSnapshot
    engine = IncidentResponseEngine(pipeline_id="test_engine")
    metrics = [MetricSnapshot(timestamp=0, metric_name="memory_percent", value=95)]
    engine.declare_incident("OOM", "test")
    engine.ingest_metrics(metrics)
    engine.diagnose()
    assert engine.incident.root_causes
    return True


def validate_uc083_layer():
    import importlib
    uc083_mod = importlib.import_module("UC-083")
    layer = uc083_mod.UCIncidentResponseLayer(pipeline_id="test_layer")
    assert layer is not None
    return True


def main():
    print("=" * 70)
    print("UC-083 — Validación Operacional Incident Response")
    print("=" * 70)

    validations = [
        ("Modelos de datos", validate_models),
        ("Analizador de logs", validate_log_analyzer),
        ("Analizador de métricas", validate_metrics_analyzer),
        ("Validador de datos", validate_data_validator),
        ("Checkpoint manager", validate_checkpoint_manager),
        ("Reprocesador", validate_reprocessor),
        ("Alert manager", validate_alert_manager),
        ("Runbook manager", validate_runbook_manager),
        ("Generador Ansible", validate_ansible_generator),
        ("Generador de monitoreo", validate_monitoring_generator),
        ("Motor de respuesta a incidentes", validate_incident_engine),
        ("Capa UC-083", validate_uc083_layer),
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
        print("  Todos los procesos de UC-083 funcionan correctamente.")
    else:
        print("  ALGUNOS PROCESOS FALLARON.")
        sys.exit(1)


if __name__ == "__main__":
    main()
