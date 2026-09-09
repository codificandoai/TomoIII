"""Mapeo de controles técnicos a obligaciones regulatorias."""
from __future__ import annotations

from typing import Any, Dict, List

from compliance_as_code.models_compliance import ComplianceRule


class ComplianceMappingEngine:
    """
    Mantiene reglas que mapean métricas técnicas a controles regulatorios
    (GDPR, CCPA, HIPAA, EU AI Act, DORA, BCBS239).
    """

    def __init__(self) -> None:
        self._rules: List[ComplianceRule] = []
        self._load_default_rules()

    def _load_default_rules(self) -> None:
        defaults = [
            ComplianceRule(
                framework="GDPR",
                article="Art.25",
                control="Privacy by Design",
                technical_metric="pii_detected_rate",
                threshold_operator="le",
                threshold_value=0.05,
                severity="high",
            ),
            ComplianceRule(
                framework="GDPR",
                article="Art.32",
                control="Security of Processing",
                technical_metric="unauthorized_access_attempts",
                threshold_operator="le",
                threshold_value=0,
                severity="critical",
            ),
            ComplianceRule(
                framework="GDPR",
                article="Art.22",
                control="Automated Decision-Making",
                technical_metric="high_impact_without_human_review",
                threshold_operator="le",
                threshold_value=0,
                severity="critical",
            ),
            ComplianceRule(
                framework="CCPA",
                article="1798.100",
                control="Consumer Rights",
                technical_metric="data_deletion_failures",
                threshold_operator="le",
                threshold_value=0,
                severity="high",
            ),
            ComplianceRule(
                framework="HIPAA",
                article="164.312",
                control="Technical Safeguards",
                technical_metric="phi_exposure_events",
                threshold_operator="le",
                threshold_value=0,
                severity="critical",
            ),
            ComplianceRule(
                framework="EU_AI_Act",
                article="Art.10",
                control="Risk Management",
                technical_metric="model_risk_score",
                threshold_operator="le",
                threshold_value=0.7,
                severity="high",
            ),
            ComplianceRule(
                framework="DORA",
                article="Art.11",
                control="Operational Resilience",
                technical_metric="recovery_time_minutes",
                threshold_operator="le",
                threshold_value=60,
                severity="high",
            ),
            ComplianceRule(
                framework="BCBS239",
                article="Principle 6",
                control="Data Quality and Accuracy",
                technical_metric="data_quality_score",
                threshold_operator="ge",
                threshold_value=0.95,
                severity="medium",
            ),
        ]
        for r in defaults:
            self._rules.append(r)

    def add_rule(self, rule: ComplianceRule) -> None:
        self._rules.append(rule)

    def evaluate_metric(self, metric_name: str, value: float) -> List[ComplianceRule]:
        violations: List[ComplianceRule] = []
        for rule in self._rules:
            if rule.technical_metric != metric_name:
                continue
            op = rule.threshold_operator
            ok = False
            if op == "le":
                ok = value <= rule.threshold_value
            elif op == "lt":
                ok = value < rule.threshold_value
            elif op == "ge":
                ok = value >= rule.threshold_value
            elif op == "gt":
                ok = value > rule.threshold_value
            elif op == "eq":
                ok = value == rule.threshold_value
            elif op == "ne":
                ok = value != rule.threshold_value
            if not ok:
                violations.append(rule)
        return violations

    def list_rules(self) -> List[ComplianceRule]:
        return list(self._rules)

    def framework_coverage(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for rule in self._rules:
            counts[rule.framework] = counts.get(rule.framework, 0) + 1
        return counts
