import pytest

from incident_types import ActionStatus, IncidentAlert, IncidentStatus, IncidentType, Severity


def make_alert(incident_type=IncidentType.UNSAFE_GENERATION, severity=Severity.CRITICAL):
    return IncidentAlert(incident_type=incident_type, severity=severity, model="test-model",
                          model_version="1.0.0", summary="test incident")


def test_handle_alert_runs_playbook_and_pauses_for_hitl(orchestrator):
    alert = make_alert()
    incident = orchestrator.handle_alert(alert)

    assert incident.playbook_name == "unsafe_generation"
    # revert_prompt_version requires_approval=true y CRITICAL no auto-aprueba
    assert incident.status == IncidentStatus.PENDING_APPROVAL
    pending = [a for a in incident.actions if a.status == ActionStatus.PENDING_APPROVAL]
    assert len(pending) == 1
    assert pending[0].name == "revert_prompt_version"


def test_low_severity_auto_approves_and_completes(orchestrator):
    alert = make_alert(severity=Severity.LOW)
    incident = orchestrator.handle_alert(alert)

    assert incident.status == IncidentStatus.REMEDIATED
    assert all(a.status != ActionStatus.PENDING_APPROVAL for a in incident.actions)
    assert incident.mttr_seconds is not None


def test_approve_pending_action_resumes_playbook(orchestrator):
    alert = make_alert()
    incident = orchestrator.handle_alert(alert)
    assert incident.status == IncidentStatus.PENDING_APPROVAL

    resumed = orchestrator.approve_pending_action(incident.incident_id, approved=True, approver="alice")
    assert resumed.status == IncidentStatus.REMEDIATED
    assert all(a.status != ActionStatus.PENDING_APPROVAL for a in resumed.actions)


def test_reject_pending_action_marks_incident_failed(orchestrator):
    alert = make_alert()
    incident = orchestrator.handle_alert(alert)

    rejected = orchestrator.approve_pending_action(incident.incident_id, approved=False, approver="bob",
                                                     comment="too risky")
    assert rejected.status == IncidentStatus.FAILED
    pending_action = next(a for a in rejected.actions if a.name == "revert_prompt_version")
    assert pending_action.status == ActionStatus.REJECTED


def test_approve_without_pending_raises(orchestrator):
    alert = make_alert(severity=Severity.LOW)
    incident = orchestrator.handle_alert(alert)  # auto-approves, nothing pending
    with pytest.raises(ValueError):
        orchestrator.approve_pending_action(incident.incident_id, approved=True, approver="alice")


def test_approve_unknown_incident_raises_keyerror(orchestrator):
    with pytest.raises(KeyError):
        orchestrator.approve_pending_action("does-not-exist", approved=True, approver="alice")


def test_rollback_incident_marks_rolled_back(orchestrator):
    alert = make_alert(severity=Severity.LOW)
    incident = orchestrator.handle_alert(alert)

    rolled_back = orchestrator.rollback_incident(incident.incident_id, reason="side effect detected")
    assert rolled_back.status == IncidentStatus.ROLLED_BACK
    assert rolled_back.rolled_back is True


def test_close_incident_records_postmortem(orchestrator):
    alert = make_alert(severity=Severity.LOW)
    incident = orchestrator.handle_alert(alert)

    closed = orchestrator.close_incident(incident.incident_id, root_cause="prompt_regression",
                                          playbook_effective=True, postmortem_notes="ok")
    assert closed.status == IncidentStatus.CLOSED
    assert closed.root_cause == "prompt_regression"
    assert closed.playbook_effective is True


def test_recurrence_last_days_counts_same_type(orchestrator):
    orchestrator.handle_alert(make_alert(incident_type=IncidentType.TOOL_FAILURE, severity=Severity.LOW))
    orchestrator.handle_alert(make_alert(incident_type=IncidentType.TOOL_FAILURE, severity=Severity.LOW))
    orchestrator.handle_alert(make_alert(incident_type=IncidentType.HALLUCINATION, severity=Severity.LOW))

    assert orchestrator.recurrence_last_days(IncidentType.TOOL_FAILURE) == 2


def test_unknown_incident_type_without_playbook_marks_failed(orchestrator, playbook_loader):
    # Elimina temporalmente el playbook de HALLUCINATION para simular un
    # tipo de incidente sin manual de procedimientos codificado.
    del playbook_loader._by_incident_type[IncidentType.HALLUCINATION]
    incident = orchestrator.handle_alert(make_alert(incident_type=IncidentType.HALLUCINATION))
    assert incident.status == IncidentStatus.FAILED
