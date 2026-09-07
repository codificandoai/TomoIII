"""
UC-083 — Tests unitarios e integración para Incident Response.
"""

import sys
import os
import csv
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from incident_models import (
    Incident, IncidentSeverity, IncidentStatus, RootCause, RootCauseCategory,
    Mitigation, MitigationType, MetricSnapshot, ValidationReport, LogEntry,
    IncidentResponseConfig,
)
from incident_engine import IncidentResponseEngine
from log_analyzer import LogAnalyzer
from metrics_analyzer import MetricsAnalyzer
from data_validator import DataValidator
from checkpoint_manager import CheckpointManager
from reprocessor import Reprocessor
from alert_manager import AlertManager
from runbook_manager import RunbookManager
from ansible_generator import AnsibleGenerator
from monitoring_generator import MonitoringGenerator
from observability_083 import ObservabilityManager


def _make_csv(row_count: int = 100, empty: bool = False):
    fd, path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["feature_1", "feature_2"])
        writer.writeheader()
        if not empty:
            for i in range(row_count):
                writer.writerow({"feature_1": str(i), "feature_2": str(i % 3)})
    return path


# ═══════════════════════════════════════════════════════════════════════════
# MODELOS
# ═══════════════════════════════════════════════════════════════════════════

class TestModels:
    def test_incident_creation(self):
        incident = Incident(title="OOM", description="test")
        assert incident.status == IncidentStatus.DETECTED

    def test_root_cause(self):
        rc = RootCause(category=RootCauseCategory.OOM, confidence=0.9, description="oom")
        assert rc.category == RootCauseCategory.OOM


# ═══════════════════════════════════════════════════════════════════════════
# LOG ANALYZER
# ═══════════════════════════════════════════════════════════════════════════

class TestLogAnalyzer:
    def test_parse_and_detect_oom(self):
        la = LogAnalyzer()
        raw = "2024-01-01T00:00:00Z ERROR orchestrator trace_id=abc123 Out of memory"
        la.parse_raw_log(raw, source="orchestrator")
        patterns = la.find_error_patterns()
        assert patterns["oom"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# METRICS ANALYZER
# ═══════════════════════════════════════════════════════════════════════════

class TestMetricsAnalyzer:
    def test_detect_sustained_high(self):
        ma = MetricsAnalyzer()
        for v in [50, 60, 70, 95, 96, 97]:
            ma.add(MetricSnapshot(timestamp=0, metric_name="memory_percent", value=v))
        assert ma.detect_sustained_high("memory_percent", 90, 3) is True


# ═══════════════════════════════════════════════════════════════════════════
# DATA VALIDATOR
# ═══════════════════════════════════════════════════════════════════════════

class TestDataValidator:
    def test_volume_pass(self):
        path = _make_csv(50)
        try:
            dv = DataValidator(IncidentResponseConfig(max_allowed_rows=10_000))
            reports = dv.validate(path)
            assert any(r.check_name == "volume" and r.passed for r in reports)
        finally:
            os.remove(path)

    def test_volume_fail(self):
        path = _make_csv(5000)
        try:
            dv = DataValidator(IncidentResponseConfig(max_allowed_rows=1000))
            reports = dv.validate(path)
            assert any(r.check_name == "volume" and not r.passed for r in reports)
        finally:
            os.remove(path)


# ═══════════════════════════════════════════════════════════════════════════
# CHECKPOINT MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestCheckpointManager:
    def test_complete_and_is_completed(self):
        tmpdir = tempfile.mkdtemp()
        cm = CheckpointManager(pipeline_id="test_pipe", checkpoint_dir=tmpdir)
        cm.create("p-001")
        cm.complete("p-001", 100)
        assert cm.is_completed("p-001")


# ═══════════════════════════════════════════════════════════════════════════
# REPROCESSOR
# ═══════════════════════════════════════════════════════════════════════════

class TestReprocessor:
    def test_reprocess(self):
        path = _make_csv(200)
        try:
            rep = Reprocessor(pipeline_id="test_reprocess")
            result = rep.reprocess(path)
            assert result["total_chunks"] >= 1
        finally:
            os.remove(path)


# ═══════════════════════════════════════════════════════════════════════════
# ALERT MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestAlertManager:
    def test_send_alert(self):
        am = AlertManager()
        am.send("P1", "OOM", "memory pressure", runbook_name="oom")
        assert len(am.list_alerts()) == 1


# ═══════════════════════════════════════════════════════════════════════════
# RUNBOOK MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestRunbookManager:
    def test_get_oom_runbook(self):
        rm = RunbookManager()
        runbook = rm.get(RootCauseCategory.OOM)
        assert "Out of Memory" in runbook["title"]


# ═══════════════════════════════════════════════════════════════════════════
# ANSIBLE GENERATOR
# ═══════════════════════════════════════════════════════════════════════════

class TestAnsibleGenerator:
    def test_generate_oom_playbook(self):
        ag = AnsibleGenerator()
        pb = ag.generate(RootCauseCategory.OOM, "test_pipe", 8, 4)
        assert "name: UC-083 Remediate OOM" in pb


# ═══════════════════════════════════════════════════════════════════════════
# MONITORING GENERATOR
# ═══════════════════════════════════════════════════════════════════════════

class TestMonitoringGenerator:
    def test_generate_prometheus_rules(self):
        mg = MonitoringGenerator()
        rules = mg.generate_prometheus_rules("test_pipe")
        assert "BatchInferenceMemoryPressure" in rules

    def test_generate_grafana_dashboard(self):
        mg = MonitoringGenerator()
        dash = mg.generate_grafana_dashboard("test_pipe")
        assert "UC-083 test_pipe" in dash["dashboard"]["title"]
        assert len(dash["dashboard"]["panels"]) >= 5

    def test_generate_loki_queries(self):
        mg = MonitoringGenerator()
        queries = mg.generate_loki_queries("test_pipe")
        assert any("OOM" in q["name"] for q in queries)

    def test_generate_envoy_config(self):
        mg = MonitoringGenerator()
        cfg = mg.generate_envoy_config("test_pipe")
        assert "listeners" in cfg["static_resources"]

    def test_generate_otel_collector_config(self):
        mg = MonitoringGenerator()
        cfg = mg.generate_otel_collector_config("test_pipe")
        assert "receivers" in cfg

    def test_write_artifacts(self):
        import tempfile
        mg = MonitoringGenerator()
        tmpdir = tempfile.mkdtemp()
        files = mg.write_artifacts("test_pipe", output_dir=tmpdir)
        assert len(files) >= 10


# ═══════════════════════════════════════════════════════════════════════════
# INCIDENT ENGINE
# ═══════════════════════════════════════════════════════════════════════════

class TestIncidentEngine:
    @pytest.fixture
    def engine(self):
        return IncidentResponseEngine(pipeline_id="test_engine")

    def test_declare(self, engine):
        incident = engine.declare_incident("OOM", "test")
        assert incident.title == "OOM"
        assert engine.incident is not None

    def test_diagnose_oom(self, engine):
        engine.declare_incident("OOM", "test")
        raw = "2024-01-01T00:00:00Z ERROR orchestrator trace_id=abc123 Out of memory\n2024-01-01T00:01:00Z ERROR worker trace_id=abc123 Killed process"
        engine.ingest_logs(raw, source="orchestrator")
        for v in [50, 70, 90, 95, 96]:
            engine.ingest_metrics([MetricSnapshot(timestamp=0, metric_name="memory_percent", value=v)])
        root_causes = engine.diagnose()
        assert any(rc.category == RootCauseCategory.OOM for rc in root_causes)

    def test_mitigate(self, engine):
        engine.declare_incident("OOM", "test")
        raw = "2024-01-01T00:00:00Z ERROR orchestrator trace_id=abc123 Out of memory"
        engine.ingest_logs(raw)
        engine.diagnose()
        mitigations = engine.mitigate()
        assert any(m.mitigation_type == MitigationType.STOP_RETRIES for m in mitigations)

    def test_full_response(self):
        engine = IncidentResponseEngine(pipeline_id="test_full")
        path = _make_csv(5000)
        try:
            raw = "2024-01-01T00:00:00Z ERROR orchestrator trace_id=abc123 Out of memory"
            metrics = [
                {"metric_name": "memory_percent", "value": 95},
                {"metric_name": "memory_percent", "value": 96},
                {"metric_name": "memory_percent", "value": 97},
            ]
            snapshots = [MetricSnapshot(timestamp=0, metric_name=m["metric_name"], value=m["value"]) for m in metrics]
            result = engine.run_full_response(
                title="OOM test",
                description="test",
                severity="P1",
                raw_logs=raw,
                metrics=snapshots,
                file_path=path,
                expected_columns=["feature_1", "feature_2"],
                historical_counts=[4000, 4100, 4200],
            )
            assert result.incident is not None
            assert result.postmortem is not None
        finally:
            os.remove(path)


# ═══════════════════════════════════════════════════════════════════════════
# API FLASK
# ═══════════════════════════════════════════════════════════════════════════

class TestAPI:
    @pytest.fixture
    def client(self):
        from api_083 import app
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_declare(self, client):
        resp = client.post("/api/v1/incident/declare", json={
            "title": "OOM",
            "description": "test",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "OOM"

    def test_full_response(self, client):
        path = _make_csv(500)
        try:
            resp = client.post("/api/v1/incident/full-response", json={
                "title": "OOM API test",
                "description": "test",
                "severity": "P1",
                "raw_logs": "2024-01-01T00:00:00Z ERROR orchestrator trace_id=abc123 Out of memory",
                "metrics": [
                    {"metric_name": "memory_percent", "value": 95},
                    {"metric_name": "memory_percent", "value": 96},
                    {"metric_name": "memory_percent", "value": 97},
                ],
                "file_path": path,
                "expected_columns": ["feature_1", "feature_2"],
                "historical_counts": [400, 410, 420],
            })
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["incident"] is not None
        finally:
            os.remove(path)
