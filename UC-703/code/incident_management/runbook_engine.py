"""Runbooks versionados y ejecutables para incidentes LLMOps."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from incident_management.models_incident import Incident, Runbook


class RunbookEngine:
    """Almacena y ejecuta runbooks determinísticos para incidentes."""

    def __init__(self) -> None:
        self._runbooks: Dict[str, Runbook] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        defaults: List[Runbook] = [
            Runbook(
                runbook_id="rb-availability",
                title="Availability incident response",
                category="availability",
                steps=[
                    {"action": "check_health", "owner": "SRE"},
                    {"action": "scale_capacity", "owner": "DevOps"},
                    {"action": "rollback_canary", "owner": "Release"},
                ],
            ),
            Runbook(
                runbook_id="rb-security",
                title="Security incident response",
                category="security",
                steps=[
                    {"action": "disable_affected_tool", "owner": "Security"},
                    {"action": "force_hitl", "owner": "SRE"},
                    {"action": "preserve_evidence", "owner": "Security"},
                    {"action": "notify_compliance", "owner": "Compliance"},
                ],
            ),
            Runbook(
                runbook_id="rb-quality",
                title="Quality degradation response",
                category="quality",
                steps=[
                    {"action": "compare_with_baseline", "owner": "QA/ML"},
                    {"action": "enable_shadow_mode", "owner": "ML"},
                    {"action": "trigger_re_evaluation", "owner": "QA"},
                ],
            ),
            Runbook(
                runbook_id="rb-compliance",
                title="Regulatory incident response",
                category="compliance",
                steps=[
                    {"action": "quarantine_data", "owner": "Security"},
                    {"action": "notify_legal", "owner": "Compliance"},
                    {"action": "initiate_audit_ledger_review", "owner": "Compliance"},
                ],
            ),
        ]
        for rb in defaults:
            self._runbooks[rb.runbook_id] = rb

    def register(self, runbook: Runbook) -> None:
        self._runbooks[runbook.runbook_id] = runbook

    def get_runbook(self, incident: Incident) -> Optional[Runbook]:
        # Match by category or tags
        if incident.category in self._runbooks:
            return self._runbooks[incident.category]
        mapping = {
            "availability": "rb-availability",
            "security": "rb-security",
            "quality": "rb-quality",
            "compliance": "rb-compliance",
        }
        rb_id = mapping.get(incident.category)
        return self._runbooks.get(rb_id)

    def execute(self, incident: Incident) -> Dict[str, Any]:
        runbook = self.get_runbook(incident)
        if not runbook:
            return {"status": "no_runbook", "executed_steps": []}
        executed = []
        for step in runbook.steps:
            executed.append({"action": step["action"], "owner": step["owner"], "status": "done"})
        return {"status": "executed", "runbook_id": runbook.runbook_id, "executed_steps": executed}

    def list_runbooks(self) -> List[Runbook]:
        return list(self._runbooks.values())
