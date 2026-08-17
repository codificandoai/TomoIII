"""UC-700 — Métricas Prometheus para autosanación avanzada.

Expone:
  - uc700_anomaly_score
  - uc700_incidents_total
  - uc700_remediation_duration_seconds
  - uc700_efficiency_pct
  - uc700_validation_checks_total
  - uc700_escalations_total
  - uc700_device_state
"""

from __future__ import annotations

from typing import Optional

try:
    from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
except ImportError:  # pragma: no cover - permite importar sin prometheus_client instalado
    CONTENT_TYPE_LATEST = "text/plain; charset=utf-8"

    def generate_latest(*_args, **_kwargs):
        return b""

    class _Metric:
        def __init__(self, *args, **kwargs):
            pass

        def set(self, *args, **kwargs):
            pass

        def inc(self, *args, **kwargs):
            pass

        def observe(self, *args, **kwargs):
            pass

    class Gauge(_Metric):
        pass

    class Counter(_Metric):
        pass

    class Histogram(_Metric):
        pass


class UC700Metrics:
    """Registro y exposición de métricas Prometheus."""

    def __init__(self, namespace: str = "uc700"):
        self.namespace = namespace
        self.anomaly_score = Gauge(
            f"{namespace}_anomaly_score",
            "Anomaly detection score per node",
            ["node_id", "device_id"],
        )
        self.incidents_total = Counter(
            f"{namespace}_incidents_total",
            "Total incidents by severity and failure class",
            ["severity", "failure_class", "scope"],
        )
        self.efficiency_pct = Gauge(
            f"{namespace}_efficiency_pct",
            "Training efficiency percentage after remediation",
            ["job_id"],
        )
        self.validation_checks_total = Counter(
            f"{namespace}_validation_checks_total",
            "Validation check results",
            ["job_id", "check", "result"],
        )
        self.escalations_total = Counter(
            f"{namespace}_escalations_total",
            "Total escalations to human operator",
            ["severity", "reason"],
        )
        self.remediation_duration_seconds = Histogram(
            f"{namespace}_remediation_duration_seconds",
            "Remediation execution duration",
            ["strategy"],
            buckets=(1, 5, 30, 60, 120, 300, 600, 1800),
        )
        self.device_state = Gauge(
            f"{namespace}_device_state",
            "Device health state (0 healthy, 1 degraded, 2 suspected, 3 quarantined, 4 failed)",
            ["node_id", "device_id", "kind"],
        )
        self.incident_state = Gauge(
            f"{namespace}_incident_state",
            "Current incident state (1 active, 0 closed)",
            ["incident_id", "node_id", "severity"],
        )

    STATE_MAP = {
        "HEALTHY": 0,
        "DEGRADED": 1,
        "SUSPECTED": 2,
        "QUARANTINED": 3,
        "FAILED": 4,
        "RECOVERING": 5,
        "VALIDATING": 6,
        "AVAILABLE": 7,
    }

    def record_anomaly(self, node_id: str, device_id: Optional[str], score: float) -> None:
        self.anomaly_score.labels(node_id=node_id, device_id=device_id or "none").set(score)

    def record_incident(self, severity: str, failure_class: str, scope: str) -> None:
        self.incidents_total.labels(severity=severity, failure_class=failure_class, scope=scope).inc()

    def record_efficiency(self, job_id: str, efficiency_pct: float) -> None:
        self.efficiency_pct.labels(job_id=job_id).set(efficiency_pct)

    def record_validation(self, job_id: str, check: str, passed: bool) -> None:
        result = "pass" if passed else "fail"
        self.validation_checks_total.labels(job_id=job_id, check=check, result=result).inc()

    def record_escalation(self, severity: str, reason: str) -> None:
        self.escalations_total.labels(severity=severity, reason=reason).inc()

    def record_device_state(self, node_id: str, device_id: str, kind: str, state: str) -> None:
        value = self.STATE_MAP.get(state.upper(), -1)
        self.device_state.labels(node_id=node_id, device_id=device_id, kind=kind).set(value)

    def record_incident_state(self, incident_id: str, node_id: str, severity: str, active: bool) -> None:
        self.incident_state.labels(incident_id=incident_id, node_id=node_id, severity=severity).set(1 if active else 0)

    def observe_remediation_duration(self, strategy: str, seconds: float) -> None:
        self.remediation_duration_seconds.labels(strategy=strategy).observe(seconds)

    def render(self) -> bytes:
        return generate_latest()
