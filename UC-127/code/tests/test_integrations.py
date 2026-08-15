from incident_types import ActionStatus, IncidentAlert, IncidentRecord, IncidentType, Severity
from integrations.collaboration_client import CollaborationClient
from integrations.gateway_client import GatewayClient
from integrations.model_router_client import ModelRouterClient
from integrations.scaling_client import ScalingClient
from integrations.siem_client import SiemClient
from integrations.ticketing_client import TicketingClient
from integrations.wiki_client import WikiClient
from playbooks.loader import PlaybookLoader
from sop_registry import SOP_REGISTRY


def make_incident(incident_type=IncidentType.DATA_LEAK, severity=Severity.CRITICAL) -> IncidentRecord:
    alert = IncidentAlert(incident_type=incident_type, severity=severity, model="m", summary="s")
    incident = IncidentRecord(alert=alert, playbook_name="data_leak")
    return incident


def get_step(playbook_name, step_name):
    loader = PlaybookLoader()
    playbook = loader.get_by_name(playbook_name)
    return next(s for s in playbook.steps if s.name == step_name)


def test_siem_send_event_dry_run_succeeds():
    incident = make_incident()
    step = get_step("data_leak", "send_to_siem")
    result = SiemClient(dry_run=True).send_event(incident, step)
    assert result.status == ActionStatus.SUCCESS


def test_collaboration_notify_security():
    incident = make_incident()
    step = get_step("data_leak", "notify_security_channel")
    result = CollaborationClient(dry_run=True).notify_security(incident, step)
    assert result.status == ActionStatus.SUCCESS


def test_gateway_block_prompt_pattern_and_rollback():
    incident = make_incident()
    step = get_step("data_leak", "block_response_pattern")
    client = GatewayClient(dry_run=True)
    result = client.block_prompt_pattern(incident, step)
    assert result.status == ActionStatus.SUCCESS
    assert result.reversible is True

    rollback_result = client.remove_rule(incident, step)
    assert rollback_result.status == ActionStatus.SUCCESS


def test_model_router_revert_and_redeploy():
    incident = make_incident()
    step = get_step("data_leak", "revert_prompt_version")
    client = ModelRouterClient(dry_run=True)
    result = client.revert_prompt_version(incident, step)
    assert result.status == ActionStatus.SUCCESS

    redeploy = client.redeploy_previous_version(incident, step)
    assert redeploy.status == ActionStatus.SUCCESS


def test_scaling_scale_out_and_scale_in():
    incident = make_incident(incident_type=IncidentType.SYSTEM_OVERLOAD)
    step = get_step("system_overload", "scale_inference_pods")
    client = ScalingClient(dry_run=True)
    result = client.scale_out(incident, step)
    assert result.status == ActionStatus.SUCCESS

    rollback_result = client.scale_in(incident, step)
    assert rollback_result.status == ActionStatus.SUCCESS


def test_ticketing_creates_compliance_ticket_unconditionally():
    incident = make_incident()
    step = get_step("data_leak", "create_compliance_ticket")
    result = TicketingClient(dry_run=True).create_ticket(incident, step)
    assert result.status == ActionStatus.SUCCESS


def test_ticketing_skips_when_not_recurrent():
    incident = make_incident(incident_type=IncidentType.PROMPT_INJECTION)
    incident.recurrence_count_7d = 0
    step = get_step("prompt_injection", "file_ticket_if_recurrent")
    result = TicketingClient(dry_run=True).create_ticket(incident, step)
    assert result.status == ActionStatus.SKIPPED


def test_ticketing_creates_when_recurrent():
    incident = make_incident(incident_type=IncidentType.PROMPT_INJECTION)
    incident.recurrence_count_7d = 999
    step = get_step("prompt_injection", "file_ticket_if_recurrent")
    result = TicketingClient(dry_run=True).create_ticket(incident, step)
    assert result.status == ActionStatus.SUCCESS


def test_wiki_append_incident_note_updates_sop_registry():
    incident = make_incident()
    incident.playbook_name = "data_leak"
    step = get_step("data_leak", "update_sop")
    before = SOP_REGISTRY.get("data_leak").update_count

    result = WikiClient(dry_run=True).append_incident_note(incident, step)
    assert result.status == ActionStatus.SUCCESS
    assert SOP_REGISTRY.get("data_leak").update_count == before + 1
    assert SOP_REGISTRY.get("data_leak").last_incident_id == incident.incident_id
