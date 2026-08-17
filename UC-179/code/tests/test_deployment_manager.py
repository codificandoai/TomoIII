import pytest


def _make_model_file(tmp_path, name="model.joblib", content=b"fake-model-v1"):
    path = tmp_path / name
    path.write_bytes(content)
    return path


def test_deploy_model_copies_and_registers_metadata(deployment, kb, tmp_path):
    model_path = _make_model_file(tmp_path)
    kb.register_model("v1", str(model_path), {"accuracy_mean": 0.9}, 10)

    metadata = deployment.deploy_model(model_path, "v1", {"accuracy_mean": 0.9})

    assert deployment.current_model_path.exists()
    assert metadata["version"] == "v1"
    assert metadata["previous_backup"] is None
    assert kb.get_deployed_model()["model_version"] == "v1"


def test_deploy_model_missing_file_raises(deployment):
    with pytest.raises(FileNotFoundError):
        deployment.deploy_model("/does/not/exist.joblib", "v1", {})


def test_second_deploy_creates_backup(deployment, kb, tmp_path):
    model_v1 = _make_model_file(tmp_path, "v1.joblib", b"model-v1")
    model_v2 = _make_model_file(tmp_path, "v2.joblib", b"model-v2")

    deployment.deploy_model(model_v1, "v1", {"accuracy_mean": 0.8})
    metadata = deployment.deploy_model(model_v2, "v2", {"accuracy_mean": 0.9})

    assert metadata["previous_backup"] is not None
    assert metadata["previous_backup"]["version"] == "v1"
    assert len(deployment.list_backups()) == 1


def test_rollback_restores_previous_version(deployment, tmp_path):
    model_v1 = _make_model_file(tmp_path, "v1.joblib", b"model-v1")
    model_v2 = _make_model_file(tmp_path, "v2.joblib", b"model-v2")

    deployment.deploy_model(model_v1, "v1", {"accuracy_mean": 0.8})
    deployment.deploy_model(model_v2, "v2", {"accuracy_mean": 0.9})

    rollback_metadata = deployment.rollback()
    assert rollback_metadata["version"] == "v1"
    assert deployment.current_model_path.read_bytes() == b"model-v1"


def test_rollback_without_backups_raises(deployment):
    with pytest.raises(RuntimeError):
        deployment.rollback()


def test_get_active_deployment_none_initially(deployment):
    assert deployment.get_active_deployment() is None
