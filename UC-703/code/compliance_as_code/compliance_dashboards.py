"""Dashboards de cumplimiento y alertado proactivo regulatorio."""
from __future__ import annotations

from typing import Any, Dict, List

from compliance_as_code.compliance_mapping_engine import ComplianceMappingEngine
from compliance_as_code.models_compliance import ComplianceAlert, ComplianceReport


class ComplianceDashboards:
    """
    Genera vistas de cumplimiento y métricas agregadas por framework regulatorio.
    """

    def __init__(self, mapping_engine: ComplianceMappingEngine) -> None:
        self.mapping = mapping_engine
        self._metric_history: Dict[str, List[float]] = {}

    def ingest_metric(self, metric_name: str, value: float) -> None:
        self._metric_history.setdefault(metric_name, []).append(value)

    def evaluate_all(self) -> Dict[str, Any]:
        summary: Dict[str, Any] = {}
        for metric_name, values in self._metric_history.items():
            if not values:
                continue
            latest = values[-1]
            violations = self.mapping.evaluate_metric(metric_name, latest)
            summary[metric_name] = {
                "latest": latest,
                "violations": [v.to_dict() for v in violations],
            }
        return summary

    def framework_scores(self) -> Dict[str, float]:
        # Simple score: 1.0 minus ratio of violated rules per framework
        framework_violations: Dict[str, int] = {}
        framework_total: Dict[str, int] = {}
        for rule in self.mapping.list_rules():
            framework_total[rule.framework] = framework_total.get(rule.framework, 0) + 1
        for metric_name, values in self._metric_history.items():
            if not values:
                continue
            violations = self.mapping.evaluate_metric(metric_name, values[-1])
            for v in violations:
                framework_violations[v.framework] = framework_violations.get(v.framework, 0) + 1
        scores: Dict[str, float] = {}
        for fw, total in framework_total.items():
            violations = framework_violations.get(fw, 0)
            scores[fw] = round(1.0 - (violations / total), 3)
        return scores

    def render_dashboard(self) -> Dict[str, Any]:
        return {
            "scores": self.framework_scores(),
            "metrics": self.evaluate_all(),
            "framework_coverage": self.mapping.framework_coverage(),
        }


class ProactiveAlerting:
    """Genera alertas proactivas cuando métricas técnicas violan umbrales regulatorios."""

    def __init__(self, mapping_engine: ComplianceMappingEngine) -> None:
        self.mapping = mapping_engine
        self._alerts: List[ComplianceAlert] = []

    def check(self, metric_name: str, value: float) -> List[ComplianceAlert]:
        violations = self.mapping.evaluate_metric(metric_name, value)
        alerts: List[ComplianceAlert] = []
        for rule in violations:
            alert = ComplianceAlert(
                rule_id=rule.rule_id,
                framework=rule.framework,
                article=rule.article,
                message=(
                    f"{rule.framework} {rule.article} '{rule.control}' violated: "
                    f"{metric_name}={value} not {rule.threshold_operator} {rule.threshold_value}"
                ),
                metric_value=value,
                threshold_value=rule.threshold_value,
                status="open",
            )
            self._alerts.append(alert)
            alerts.append(alert)
        return alerts

    def acknowledge(self, alert_id: str) -> Optional[ComplianceAlert]:
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.status = "acknowledged"
                return alert
        return None

    def resolve(self, alert_id: str) -> Optional[ComplianceAlert]:
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.status = "resolved"
                return alert
        return None

    def open_alerts(self) -> List[ComplianceAlert]:
        return [a for a in self._alerts if a.status == "open"]

    def generate_compliance_report(self) -> ComplianceReport:
        open_alerts = self.open_alerts()
        scores = {}  # caller can fill using dashboard
        overall = "compliant" if not open_alerts else "at_risk"
        if any(a.framework in ("HIPAA", "GDPR") for a in open_alerts):
            overall = "non_compliant"
        return ComplianceReport(
            overall_status=overall,
            framework_scores=scores,
            open_alerts=len(open_alerts),
            evidence_count=len(self._alerts),
            findings=[a.message for a in open_alerts],
        )
