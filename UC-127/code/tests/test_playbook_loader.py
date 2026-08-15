from incident_types import IncidentType


def test_all_incident_types_have_a_playbook(playbook_loader):
    for incident_type in IncidentType:
        playbook = playbook_loader.get_by_incident_type(incident_type)
        assert playbook is not None, f"Falta playbook para {incident_type}"
        assert len(playbook.steps) > 0


def test_get_by_name(playbook_loader):
    playbook = playbook_loader.get_by_name("data_leak")
    assert playbook is not None
    assert playbook.incident_type == IncidentType.DATA_LEAK


def test_list_playbooks_not_empty(playbook_loader):
    playbooks = playbook_loader.list_playbooks()
    assert len(playbooks) >= 9


def test_unknown_playbook_name_returns_none(playbook_loader):
    assert playbook_loader.get_by_name("does_not_exist") is None
