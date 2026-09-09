"""Controller de Compliance as Code."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from compliance_as_code.access_control_enforcer import AccessControlEnforcer
from compliance_as_code.compliance_dashboards import ComplianceDashboards, ProactiveAlerting
from compliance_as_code.compliance_mapping_engine import ComplianceMappingEngine
from compliance_as_code.data_lineage_tracker import DataLineageTracker
from compliance_as_code.inference_audit_ledger import InferenceAuditLedger
from compliance_as_code.models_compliance import (
    AccessDecision,
    ArtifactBundle,
    ComplianceAlert,
    ComplianceRule,
    DatasetLineage,
    InferenceAuditRecord,
    PromptVersion,
)
from compliance_as_code.prompt_version_control import PromptVersionControl


class ComplianceController:
    """
    Orquesta el cumplimiento incrustado en cada etapa del pipeline de LLMOps.
    """

    def __init__(
        self,
        prompt_versioning: Optional[PromptVersionControl] = None,
        data_lineage: Optional[DataLineageTracker] = None,
        inference_ledger: Optional[InferenceAuditLedger] = None,
        access_control: Optional[AccessControlEnforcer] = None,
        mapping_engine: Optional[ComplianceMappingEngine] = None,
        dashboards: Optional[ComplianceDashboards] = None,
        alerting: Optional[ProactiveAlerting] = None,
    ) -> None:
        self.prompt_versioning = prompt_versioning or PromptVersionControl()
        self.data_lineage = data_lineage or DataLineageTracker()
        self.inference_ledger = inference_ledger or InferenceAuditLedger()
        self.access_control = access_control or AccessControlEnforcer()
        self.mapping = mapping_engine or ComplianceMappingEngine()
        self.dashboards = dashboards or ComplianceDashboards(self.mapping)
        self.alerting = alerting or ProactiveAlerting(self.mapping)

    # ------------------------------------------------------------------
    # Prompt version control
    # ------------------------------------------------------------------
    def commit_prompt(
        self,
        prompt_name: str,
        content: str,
        author: str,
        regulatory_change: bool = False,
        approved_by: Optional[List[str]] = None,
        commit_message: str = "",
    ) -> PromptVersion:
        return self.prompt_versioning.commit(
            prompt_name=prompt_name,
            content=content,
            author=author,
            regulatory_change=regulatory_change,
            approved_by=approved_by,
            commit_message=commit_message,
        )

    def approve_prompt(self, prompt_name: str, version_id: str, approver: str) -> Optional[PromptVersion]:
        return self.prompt_versioning.approve(prompt_name, version_id, approver)

    def prompt_history(self, prompt_name: str) -> List[PromptVersion]:
        return self.prompt_versioning.history(prompt_name)

    # ------------------------------------------------------------------
    # Data lineage
    # ------------------------------------------------------------------
    def register_dataset(
        self,
        dataset_id: str,
        source: str,
        transformations: Optional[List[Dict[str, Any]]] = None,
        consent_tags: Optional[List[str]] = None,
        retention_hours: float = 168.0,
        purpose: str = "",
        privacy_controls: Optional[List[str]] = None,
    ) -> DatasetLineage:
        return self.data_lineage.register(
            dataset_id=dataset_id,
            source=source,
            transformations=transformations,
            consent_tags=consent_tags,
            retention_hours=retention_hours,
            purpose=purpose,
            privacy_controls=privacy_controls,
        )

    def add_dataset_transformation(
        self,
        dataset_id: str,
        name: str,
        description: str,
        tool: str = "",
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[DatasetLineage]:
        return self.data_lineage.add_transformation(dataset_id, name, description, tool, params)

    def get_dataset_lineage(self, dataset_id: str) -> Optional[DatasetLineage]:
        return self.data_lineage.get(dataset_id)

    # ------------------------------------------------------------------
    # Access control
    # ------------------------------------------------------------------
    def grant_role(
        self,
        role: str,
        resource: str,
        action: str,
        environments: Optional[List[str]] = None,
    ) -> None:
        self.access_control.grant_role(role, resource, action, environments)

    def evaluate_access(
        self,
        requester_id: str,
        roles: List[str],
        resource: str,
        action: str,
        environment: str,
        oidc_claims: Optional[Dict[str, Any]] = None,
        tenant: str = "",
    ) -> AccessDecision:
        return self.access_control.evaluate(
            requester_id=requester_id,
            roles=roles,
            resource=resource,
            action=action,
            environment=environment,
            oidc_claims=oidc_claims,
            tenant=tenant,
        )

    # ------------------------------------------------------------------
    # Inference audit ledger
    # ------------------------------------------------------------------
    def record_inference(
        self,
        request_id: str,
        session_id: str,
        requester_id: str,
        requester_roles: List[str],
        artifact_bundle: ArtifactBundle,
        input_text: str,
        output_text: str,
        access_decision: str,
        policies_applied: List[str],
        pii_detected: bool = False,
        guardrail_violations: Optional[List[str]] = None,
        e_discovery_tag: str = "",
    ) -> InferenceAuditRecord:
        return self.inference_ledger.record(
            request_id=request_id,
            session_id=session_id,
            requester_id=requester_id,
            requester_roles=requester_roles,
            artifact_bundle=artifact_bundle,
            input_text=input_text,
            output_text=output_text,
            access_decision=access_decision,
            policies_applied=policies_applied,
            pii_detected=pii_detected,
            guardrail_violations=guardrail_violations,
            e_discovery_tag=e_discovery_tag,
        )

    def query_inference_audit(
        self,
        request_id: str = "",
        session_id: str = "",
        requester_id: str = "",
        tag: str = "",
    ) -> List[InferenceAuditRecord]:
        if request_id:
            return self.inference_ledger.query_by_request(request_id)
        if session_id:
            return self.inference_ledger.query_by_session(session_id)
        if requester_id:
            return self.inference_ledger.query_by_requester(requester_id)
        if tag:
            return self.inference_ledger.query_by_tag(tag)
        return self.inference_ledger.list_records()

    def verify_ledger(self) -> bool:
        return self.inference_ledger.verify_chain()

    # ------------------------------------------------------------------
    # Compliance mapping / alerting / dashboards
    # ------------------------------------------------------------------
    def add_compliance_rule(self, rule: ComplianceRule) -> None:
        self.mapping.add_rule(rule)

    def ingest_metric(self, metric_name: str, value: float) -> List[ComplianceAlert]:
        self.dashboards.ingest_metric(metric_name, value)
        return self.alerting.check(metric_name, value)

    def acknowledge_alert(self, alert_id: str) -> Optional[ComplianceAlert]:
        return self.alerting.acknowledge(alert_id)

    def resolve_alert(self, alert_id: str) -> Optional[ComplianceAlert]:
        return self.alerting.resolve(alert_id)

    def compliance_report(self) -> Dict[str, Any]:
        report = self.alerting.generate_compliance_report()
        report.framework_scores = self.dashboards.framework_scores()
        return report.to_dict()

    def dashboard(self) -> Dict[str, Any]:
        return self.dashboards.render_dashboard()

    def list_rules(self) -> List[ComplianceRule]:
        return self.mapping.list_rules()
