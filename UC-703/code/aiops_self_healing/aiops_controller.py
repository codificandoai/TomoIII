"""Controller de AIOps Self-Healing Platform para UC-703."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from aiops_self_healing.communication_and_audit import AuditLedger, CommunicationEngine
from aiops_self_healing.diagnostic_engine import DiagnosticEngine
from aiops_self_healing.event_correlator import EventCorrelator
from aiops_self_healing.event_ingestion_orchestrator import EventIngestionOrchestrator
from aiops_self_healing.models_aiops import (
    AIOpsState,
    CommunicationRecord,
    CorrelationGroup,
    NormalizedAlert,
    RawEvent,
    RemediationAction,
    RemediationPolicy,
    RemediationType,
    SelfHealingReport,
)
from aiops_self_healing.remediation_orchestrator import RemediationOrchestrator
from aiops_self_healing.risk_policy_engine import RiskPolicyEngine, SeverityClassifier


class AIOpsController:
    """
    Orquesta el flujo completo AIOps:
    ingesta -> normalización -> correlación -> diagnóstico -> remediación
    -> validación -> resolución/escalamiento, con comunicaciones y auditoría.
    """

    def __init__(
        self,
        ingestion: Optional[EventIngestionOrchestrator] = None,
        correlator: Optional[EventCorrelator] = None,
        diagnostics: Optional[DiagnosticEngine] = None,
        policy: Optional[RiskPolicyEngine] = None,
        remediation: Optional[RemediationOrchestrator] = None,
        comms: Optional[CommunicationEngine] = None,
        audit: Optional[AuditLedger] = None,
    ) -> None:
        self.ingestion = ingestion or EventIngestionOrchestrator()
        self.correlator = correlator or EventCorrelator()
        self.diagnostics = diagnostics or DiagnosticEngine()
        self.policy = policy or RiskPolicyEngine()
        self.remediation = remediation or RemediationOrchestrator(self.policy)
        self.comms = comms or CommunicationEngine()
        self.audit = audit or AuditLedger()
        self._group_states: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # Event ingestion / normalization
    # ------------------------------------------------------------------
    def ingest_event(self, source: str, payload: Dict[str, Any]) -> NormalizedAlert:
        return self.ingestion.ingest_and_normalize(source, payload)

    def list_events(self) -> List[RawEvent]:
        return self.ingestion.list_events()

    def list_alerts(self) -> List[NormalizedAlert]:
        return self.ingestion.list_alerts()

    # ------------------------------------------------------------------
    # Correlation
    # ------------------------------------------------------------------
    def correlate_alerts(self) -> List[CorrelationGroup]:
        return self.correlator.correlate(self.ingestion.list_alerts())

    # ------------------------------------------------------------------
    # Diagnose + remediate
    # ------------------------------------------------------------------
    def process_group(
        self,
        group_id: str,
        approver: str = "",
    ) -> SelfHealingReport:
        group = next((g for g in self.correlator.list_groups() if g.group_id == group_id), None)
        if not group:
            raise ValueError(f"Group {group_id} not found")

        self._group_states[group_id] = AIOpsState.DIAGNOSING.value
        alerts = [a for a in self.ingestion.list_alerts() if a.alert_id in group.alert_ids]
        diagnosis = self.diagnostics.diagnose(group, alerts)

        self._group_states[group_id] = AIOpsState.REMEDIATING.value
        actions: List[RemediationAction] = []
        for action_type in diagnosis.proposed_remediations:
            action = self.remediation.execute(
                group,
                action_type,
                target=group.resource or "system",
                params={"severity": group.severity},
                approver=approver if action_type.value in {"rollback_model", "rollback_config", "sandbox_isolation", "fallback_provider"} else "",
            )
            if action:
                actions.append(action)

        self._group_states[group_id] = AIOpsState.VALIDATING.value
        # deterministic validation: health_test if present and critical actions succeeded
        health_actions = [a for a in actions if a.action_type == RemediationType.HEALTH_TEST.value]
        failed = [a for a in actions if a.status in {"failed", "pending_approval"}]

        if failed and group.severity in {"critical", "high"}:
            state = AIOpsState.ESCALATED.value
            decision = "Escalated to human due to failed/pending remediation"
        else:
            state = AIOpsState.RESOLVED.value if not failed else AIOpsState.VALIDATING.value
            decision = "Auto-remediation executed and validated" if not failed else "Partial remediation; validation pending"

        self._group_states[group_id] = state

        # Communications
        comms: List[CommunicationRecord] = []
        if diagnosis.requires_human_review or state == AIOpsState.ESCALATED.value:
            comms.append(
                self.comms.send(
                    group_id=group_id,
                    channel="pager",
                    recipient="SRE",
                    template_name="escalation",
                    variables={
                        "group_id": group_id,
                        "summary": diagnosis.summary,
                        "severity": group.severity,
                        "owner": approver or "on-call",
                        "reason": decision,
                    },
                )
            )
        comms.append(
            self.comms.send(
                group_id=group_id,
                channel="slack",
                recipient="llmops-alerts",
                template_name="incident_opened",
                variables={
                    "group_id": group_id,
                    "summary": diagnosis.summary,
                    "severity": group.severity,
                    "state": state,
                    "owner": approver or "aiops-controller",
                },
            )
        )

        # Audit record
        raw_event_ids = [a.event_id for a in alerts]
        audit_record = self.audit.record(
            group_id=group_id,
            state=state,
            decision=decision,
            responsible=approver or "aiops-controller",
            raw_event_ids=raw_event_ids,
            alert_ids=group.alert_ids,
            diagnosis_id=diagnosis.diagnosis_id,
            remediation_ids=[a.action_id for a in actions],
            outcome=state,
            approvals=[approver] if approver else [],
        )

        return SelfHealingReport(
            group_id=group_id,
            state=state,
            diagnosis=diagnosis,
            actions=actions,
            audit_record=audit_record,
            communications=comms,
        )

    def run_full_pipeline(
        self,
        events: List[Dict[str, Any]],
        approver: str = "",
    ) -> List[SelfHealingReport]:
        for ev in events:
            self.ingest_event(ev["source"], ev["payload"])
        self.correlate_alerts()
        reports = []
        for group in self.correlator.list_groups():
            reports.append(self.process_group(group.group_id, approver=approver))
        return reports

    # ------------------------------------------------------------------
    # Policy / actions helpers
    # ------------------------------------------------------------------
    def register_policy(self, policy: RemediationPolicy) -> None:
        self.policy.register(policy)

    def rollback_action(self, action_id: str) -> Optional[RemediationAction]:
        return self.remediation.rollback(action_id)

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    def dashboard(self) -> Dict[str, Any]:
        return {
            "events": len(self.ingestion.list_events()),
            "alerts": len(self.ingestion.list_alerts()),
            "groups": len(self.correlator.list_groups()),
            "actions": len(self.remediation.list_actions()),
            "communications": len(self.comms.list_records()),
            "audit_records": len(self.audit.list_records()),
            "group_states": dict(self._group_states),
        }
