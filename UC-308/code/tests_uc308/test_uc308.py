"""
UC-308 — Tests unitarios e integración para Agent Drift / Environmental Degradation.

Cubre:
- Healthy baseline y ausencia de drift.
- API schema drift.
- HTML selector drift.
- Data distribution shift (PSI/JS).
- Latency / resource regression.
- Behavioral / quality regression.
- Supresión de alertas por ventanas/histéresis.
- Mitigación crítica y recomendaciones.
- Golden dataset firmado/hash e integridad.
- API REST Flask (cards, endpoints, métricas).
- Flujo end-to-end.
"""

from __future__ import annotations

import json
import time

import pytest

from drift_orchestrator import DriftOrchestrator
from environment_simulator import SimulatedExternalEnvironment
from golden_dataset import build_default_golden_dataset
from models_308 import (
    DriftConfig,
    DriftStatus,
    DriftType,
    RecommendationAction,
    SystemStatus,
)


def _run_scenario(orchestrator: DriftOrchestrator, scenario: str) -> None:
    return orchestrator.run_evaluation(trigger="test", scenario=scenario)


def test_healthy_baseline(orchestrator: DriftOrchestrator):
    run = _run_scenario(orchestrator, "healthy")
    assert run.system_status == SystemStatus.NORMAL
    assert run.aggregate["success_rate"] == pytest.approx(1.0, abs=0.01)
    assert run.aggregate["quality_score"] >= 0.8
    assert len(run.drift_signals) == 0


def test_api_schema_change_produces_contract_drift(orchestrator: DriftOrchestrator):
    run = _run_scenario(orchestrator, "api_schema_change")
    api_signals = [s for s in run.drift_signals if s.drift_type == DriftType.CONTRACT_API]
    assert len(api_signals) >= 1
    assert any(s.status in (DriftStatus.WARNING, DriftStatus.DEGRADED, DriftStatus.CRITICAL) for s in api_signals)
    # Recomendación de deshabilitar la herramienta afectada en UC-300.
    recs = orchestrator.alert_manager.alerts[-1].recommendations if orchestrator.alert_manager.alerts else []
    # Asegurar que, si se generó alerta, la recomendación existe.
    if orchestrator.alert_manager.alerts and orchestrator.alert_manager.alerts[-1].run_id == run.run_id:
        actions = [r.action for r in recs]
        assert RecommendationAction.DISABLE_TOOL_UC300 in actions


def test_html_selector_change_produces_interface_drift(orchestrator: DriftOrchestrator):
    run = _run_scenario(orchestrator, "html_selector_change")
    html_signals = [s for s in run.drift_signals if s.drift_type == DriftType.HTML_INTERFACE]
    assert len(html_signals) >= 1
    assert any(s.status != DriftStatus.NORMAL for s in html_signals)


def test_data_distribution_shift_produces_distribution_drift(orchestrator: DriftOrchestrator):
    run = _run_scenario(orchestrator, "data_distribution_shift")
    dist_signals = [s for s in run.drift_signals if s.drift_type == DriftType.DATA_DISTRIBUTION]
    assert len(dist_signals) >= 1
    numeric = [s for s in dist_signals if s.dimension == "numeric_distribution"]
    categorical = [s for s in dist_signals if s.dimension == "categorical_distribution"]
    assert numeric or categorical
    assert all(s.status != DriftStatus.NORMAL for s in dist_signals)


def test_latency_and_resource_regression(orchestrator: DriftOrchestrator):
    run = _run_scenario(orchestrator, "latency_regression")
    op_signals = [s for s in run.drift_signals if s.drift_type == DriftType.TOOL_OPERATIONAL]
    assert len(op_signals) >= 1
    latencies = [s for s in op_signals if "latency" in s.dimension]
    resources = [s for s in op_signals if "resource_" in s.dimension]
    assert latencies or resources
    assert any(s.status != DriftStatus.NORMAL for s in op_signals)


def test_behavioral_and_quality_regression(orchestrator: DriftOrchestrator):
    run = _run_scenario(orchestrator, "behavioral_regression")
    behavioral = [s for s in run.drift_signals if s.drift_type == DriftType.BEHAVIORAL]
    assert len(behavioral) >= 1
    assert all(s.status != DriftStatus.NORMAL for s in behavioral)
    assert run.aggregate["uc300_block_total"] > 0 or run.aggregate["uc290_override_total"] > 0


def test_consecutive_window_alert_suppression(orchestrator: DriftOrchestrator):
    config = orchestrator.config
    # Una corrida degradada no debería alertar aún (hysteresis).
    # Usamos data_distribution_shift porque genera un estado degradado estable.
    run1 = _run_scenario(orchestrator, "data_distribution_shift")
    assert run1.system_status == SystemStatus.DEGRADED
    initial_alerts = len([a for a in orchestrator.alert_manager.alerts if a.run_id == run1.run_id])
    assert initial_alerts == 0

    # Segunda corrida degradada consecutiva -> alerta.
    run2 = _run_scenario(orchestrator, "data_distribution_shift")
    assert run2.system_status == SystemStatus.DEGRADED
    alerts_for_r2 = [a for a in orchestrator.alert_manager.alerts if a.run_id == run2.run_id]
    assert len(alerts_for_r2) >= 1

    _run_scenario(orchestrator, "healthy")
    _run_scenario(orchestrator, "healthy")
    assert orchestrator.alert_manager.get_active_alerts() == []
    assert all(a.resolved for a in alerts_for_r2)


def test_critical_mitigation_recommends_containment(orchestrator: DriftOrchestrator):
    run = _run_scenario(orchestrator, "error_regression")
    assert run.system_status == SystemStatus.CRITICAL
    critical_alerts = [a for a in orchestrator.alert_manager.alerts if a.run_id == run.run_id]
    assert len(critical_alerts) >= 1
    actions = {r.action for alert in critical_alerts for r in alert.recommendations}
    assert RecommendationAction.CONTAINMENT_ROLLBACK_UC324 in actions


def test_golden_dataset_signature_and_tamper():
    dataset = build_default_golden_dataset()
    secret = "uc308-secret-key"

    dataset.sign(secret)
    assert dataset.verify_signature(secret)
    assert dataset.verify_integrity()
    assert not dataset.verify_signature("wrong-key")

    # Tamper: cambiar versión rompe integridad.
    original = dataset.version
    dataset.version = "tampered"
    assert not dataset.verify_integrity()
    dataset.version = original

    # Tamper: añadir un caso también rompe integridad.
    from models_308 import GoldenCase
    dataset.cases.append(GoldenCase(id="TAMPER", name="tamper", description="tamper", tool="x", environment="default", agent_version="1.0.0"))
    assert not dataset.verify_integrity()


def test_api_health_and_schema(api_client):
    resp = api_client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"

    resp = api_client.get("/api/v1/schema")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "input_cards" in data and "output_cards" in data
    assert "POST /api/v1/run-evaluation" in data["input_cards"]


def test_api_run_evaluation_and_metrics(api_client):
    # Reset para partir de un estado limpio y asegurar baselines.
    api_client.post("/api/v1/reset", json={"reinitialize": True})

    resp = api_client.post("/api/v1/run-evaluation", json={"scenario": "api_schema_change"})
    assert resp.status_code == 200
    run = resp.get_json()
    assert "run_id" in run
    assert "system_status" in run
    assert run["trigger"] == "manual"
    # Asegurar serializable JSON.
    json.dumps(run)

    status_resp = api_client.get("/api/v1/status")
    assert status_resp.status_code == 200
    status = status_resp.get_json()
    assert status["run_count"] >= 2  # baseline + eval

    metrics_resp = api_client.get("/api/v1/metrics")
    assert metrics_resp.status_code == 200
    assert metrics_resp.content_type.startswith("text/plain")
    body = metrics_resp.get_data(as_text=True)
    assert "uc308_run_status" in body
    assert "uc308_success_rate" in body
    assert "uc308_task_results_total" in body


def test_api_datasets_excludes_secret_payloads(api_client):
    resp = api_client.get("/api/v1/datasets")
    assert resp.status_code == 200
    data = resp.get_json()
    # Sin include_secret, no se exponen payloads sensibles.
    public_cases = data.get("public_cases", [])
    for case in public_cases:
        assert "input_payload" not in case
        assert "expected_output" not in case


def test_full_end_to_end():
    config = DriftConfig()
    dataset = build_default_golden_dataset(version="e2e-1.0.0")
    env = SimulatedExternalEnvironment(seed=99999)
    orchestrator = DriftOrchestrator(
        config=config,
        dataset=dataset,
        environment=env,
    )

    # Baseline sano
    init = orchestrator.initialize_baselines(scenario="healthy")
    assert init["baselines_created"] == len({c.tool for c in dataset.cases})

    # Healthy normal
    healthy = _run_scenario(orchestrator, "healthy")
    assert healthy.system_status == SystemStatus.NORMAL

    # Data distribution drift degradado -> dos veces para generar alerta
    _run_scenario(orchestrator, "data_distribution_shift")
    drift_run = _run_scenario(orchestrator, "data_distribution_shift")
    assert drift_run.system_status == SystemStatus.DEGRADED
    alerts = orchestrator.alert_manager.get_active_alerts()
    assert len(alerts) >= 1

    # Métricas exportables
    metrics = orchestrator.get_metrics()
    assert "uc308_alerts_total" in metrics
    assert "uc308_drift_score" in metrics
    assert "uc308_drift_status" in metrics

    # Historial y resets
    assert len(orchestrator.get_history()) >= 4
    orchestrator.reset()
    assert len(orchestrator.get_history()) == 0
    assert len(orchestrator.alert_manager.alerts) == 0


def test_nightly_scheduler_due():
    from nightly_scheduler import NightlyScheduler
    # Cada minuto 0
    sched = NightlyScheduler("0 * * * *")
    # Un timestamp cuyo UTC es minuto 0
    t0 = 1704067200.0  # 2024-01-01 00:00:00 UTC aprox
    assert sched.is_due(t0)
    sched.mark_run(t0)
    assert not sched.is_due(t0 + 30)  # mismo minuto
    assert sched.is_due(t0 + 3600)   # siguiente hora en punto
