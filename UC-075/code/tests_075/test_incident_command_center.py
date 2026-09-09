"""Tests para incident_command_center.py — StackStorm + Wiki.js + ICC."""
from __future__ import annotations

import pytest

from incident_command_center import (
    ActionStatus,
    ApprovalScope,
    IncidentCommandCenter,
    IncidentPageType,
    StackStormAction,
    StackStormAdapter,
    WikiJsAdapter,
    WikiPage,
)


class TestStackStormAdapter:
    def test_auto_action_executed_with_approval_ref(self):
        st2 = StackStormAdapter()
        a = st2.submit(
            action="notify_team",
            params={"message": "x"},
            incident_id="inc-1",
            approval_ref="auto-policy-1",
        )
        executed = st2.execute(a.action_id)
        assert executed.status == ActionStatus.EXECUTED

    def test_hitl_action_requires_explicit_scope(self):
        st2 = StackStormAdapter()
        a = st2.submit(
            action="revoke_credentials",
            params={},
            incident_id="inc-1",
            approval_ref="auto-policy-1",
            scope=ApprovalScope.AUTO.value,
        )
        executed = st2.execute(a.action_id)
        assert executed.status == ActionStatus.REJECTED
        assert "HITL" in executed.result["error"]

    def test_missing_approval_ref_rejects(self):
        st2 = StackStormAdapter()
        a = st2.submit(
            action="notify_team",
            params={},
            incident_id="inc-1",
            approval_ref="",
        )
        executed = st2.execute(a.action_id)
        assert executed.status == ActionStatus.REJECTED

    def test_action_not_in_allowlist_rejected(self):
        st2 = StackStormAdapter()
        a = st2.submit(
            action="undefined_action",
            params={},
            incident_id="inc-1",
            approval_ref="ref",
        )
        executed = st2.execute(a.action_id)
        assert executed.status == ActionStatus.REJECTED

    def test_rollback(self):
        st2 = StackStormAdapter()
        a = st2.submit("notify_team", {}, "inc-1", "ref")
        st2.execute(a.action_id)
        rolled = st2.rollback(a.action_id)
        assert rolled.status == ActionStatus.ROLLED_BACK


class TestWikiJsAdapter:
    def test_create_incident_page(self):
        wiki = WikiJsAdapter()
        page = wiki.create_page(
            IncidentPageType.INCIDENT,
            "Incident inc-1",
            "details",
            incident_id="inc-1",
        )
        assert page.page_type == IncidentPageType.INCIDENT
        assert len(wiki.get_pages_for_incident("inc-1")) == 1

    def test_postmortem(self):
        wiki = WikiJsAdapter()
        page = wiki.create_postmortem(
            incident_id="inc-1",
            title="Postmortem",
            findings=["f1"],
            action_items=["a1"],
            participants=["ana"],
        )
        assert page.page_type == IncidentPageType.POSTMORTEM
        assert "f1" in page.content

    def test_runbook_page(self):
        wiki = WikiJsAdapter()
        page = wiki.create_runbook_page("jailbreak", ["block", "log"], "v2")
        assert page.page_type == IncidentPageType.RUNBOOK
        assert "block" in page.content

    def test_search(self):
        wiki = WikiJsAdapter()
        wiki.create_page(IncidentPageType.INCIDENT, "Incidente", "malware")
        results = wiki.search("malware")
        assert results


class TestIncidentCommandCenter:
    def test_report_incident_creates_wiki_page(self):
        icc = IncidentCommandCenter()
        inc = icc.report_incident(
            incident_id="inc-1",
            title="tool abuse",
            description="agent deleted bucket",
            category="tool_abuse",
            severity="high",
        )
        assert inc.incident_id == "inc-1"
        view = icc.unified_view("inc-1")
        assert view["incident"]["incident_id"] == "inc-1"
        assert len(view["wiki_pages"]) == 1

    def test_auto_action_submitted_and_executed(self):
        icc = IncidentCommandCenter()
        action = icc.submit_action(
            incident_id="inc-1",
            action="notify_team",
            params={"channel": "#ops"},
            approval_ref="auto-1",
        )
        assert action.status == ActionStatus.EXECUTED

    def test_hitl_action_stays_pending(self):
        icc = IncidentCommandCenter()
        action = icc.submit_action(
            incident_id="inc-1",
            action="revoke_credentials",
            params={},
            approval_ref="hitl-1",
            scope=ApprovalScope.HITL.value,
        )
        assert action.status == ActionStatus.PENDING

    def test_execute_approved_hitl_action(self):
        icc = IncidentCommandCenter()
        action = icc.submit_action(
            incident_id="inc-1",
            action="revoke_credentials",
            params={},
            approval_ref="hitl-1",
            scope=ApprovalScope.HITL.value,
        )
        executed = icc.execute_approved_action(action.action_id)
        assert executed.status == ActionStatus.EXECUTED

    def test_postmortem_and_runbook(self):
        icc = IncidentCommandCenter()
        icc.report_incident("inc-1", "x", "y", "cat", "sev")
        pm = icc.create_postmortem("inc-1", "Post", ["f1"], ["a1"], ["ana"])
        assert pm.page_type == IncidentPageType.POSTMORTEM
        rb = icc.sync_runbook("cat", ["a", "b"], "v1")
        assert rb.page_type == IncidentPageType.RUNBOOK

    def test_status_board(self):
        icc = IncidentCommandCenter()
        icc.report_incident("inc-1", "x", "y", "cat", "high")
        board = icc.status_board()
        assert board["total_incidents"] == 1
        assert board["by_severity"]["high"] == 1


class TestOrchestratorIntegration:
    def test_orchestrator_icc_report_and_view(self):
        from continuous_training_orchestrator import ContinuousTrainingOrchestrator
        orch = ContinuousTrainingOrchestrator()
        inc = orch.icc_report_incident(
            incident_id="inc-99",
            title="Data leak",
            description="PII exposed",
            category="pii_leak",
            severity="critical",
            owner="security@utron.ai",
        )
        assert inc["incident_id"] == "inc-99"
        view = orch.icc_unified_view("inc-99")
        assert view["incident"]["incident_id"] == "inc-99"

    def test_orchestrator_icc_action_requires_approval(self):
        from continuous_training_orchestrator import ContinuousTrainingOrchestrator
        orch = ContinuousTrainingOrchestrator()
        action = orch.icc_submit_action(
            incident_id="inc-99",
            action="disable_tool",
            params={},
            approval_ref="",
            scope="auto",
        )
        assert action["status"] == "pending"
        executed = orch.icc_execute_action(action["action_id"])
        assert executed["status"] == "rejected"

    def test_orchestrator_status_board(self):
        from continuous_training_orchestrator import ContinuousTrainingOrchestrator
        orch = ContinuousTrainingOrchestrator()
        orch.icc_report_incident("inc-1", "t", "d", "cat", "low")
        board = orch.icc_status_board()
        assert board["total_incidents"] >= 1
