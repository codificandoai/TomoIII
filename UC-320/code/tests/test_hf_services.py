"""Tests unitarios para los 8 servicios de Hugging Face en UC-320."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# --- HFServices aggregator ---
def test_hf_services_status():
    from hf_services import HFServices
    svc = HFServices(backend="mock")
    status = svc.status()
    assert status["backend"] == "mock"
    assert "services" in status
    assert "inference_endpoints" in status["services"]


# --- Inference Endpoints ---
def test_endpoint_create():
    from hf_services import InferenceEndpointManager, EndpointStatus
    mgr = InferenceEndpointManager(backend="mock")
    ep = mgr.create(name="test-ep", model_id="mock/sentiment-mock")
    assert ep.status == EndpointStatus.RUNNING
    assert ep.url


def test_endpoint_list():
    from hf_services import InferenceEndpointManager
    mgr = InferenceEndpointManager(backend="mock")
    mgr.create(name="ep1", model_id="m1")
    mgr.create(name="ep2", model_id="m2")
    eps = mgr.list_endpoints()
    assert len(eps) == 2


def test_endpoint_stop():
    from hf_services import InferenceEndpointManager, EndpointStatus
    mgr = InferenceEndpointManager(backend="mock")
    ep = mgr.create(name="test", model_id="m")
    result = mgr.stop(ep.endpoint_id)
    assert result["stopped"]
    assert mgr.get(ep.endpoint_id).status == EndpointStatus.STOPPED


def test_endpoint_delete():
    from hf_services import InferenceEndpointManager
    mgr = InferenceEndpointManager(backend="mock")
    ep = mgr.create(name="test", model_id="m")
    result = mgr.delete(ep.endpoint_id)
    assert result["deleted"]
    assert mgr.get(ep.endpoint_id) is None


def test_endpoint_health():
    from hf_services import InferenceEndpointManager
    mgr = InferenceEndpointManager(backend="mock")
    ep = mgr.create(name="test", model_id="m")
    health = mgr.health_check(ep.endpoint_id)
    assert health["healthy"]


# --- Datasets ---
def test_dataset_load():
    from hf_services import DatasetManager
    dm = DatasetManager(backend="mock")
    record = dm.load("ORG/test-ds", revision="v1", split="train", pii_checked=True)
    assert record.num_rows > 0
    assert "text" in record.features


def test_dataset_stream():
    from hf_services import DatasetManager
    dm = DatasetManager(backend="mock")
    dm.load("ORG/test-ds", split="train")
    batches = list(dm.stream("ORG/test-ds", split="train", batch_size=5))
    assert len(batches) >= 1


def test_dataset_transform_filter():
    from hf_services import DatasetManager
    dm = DatasetManager(backend="mock")
    dm.load("ORG/test-ds", split="train")
    result = dm.transform("ORG/test-ds", "main", "train", "filter", {"threshold": 2})
    assert result["transformed"]


def test_dataset_transform_map():
    from hf_services import DatasetManager
    dm = DatasetManager(backend="mock")
    dm.load("ORG/test-ds", split="train")
    result = dm.transform("ORG/test-ds", "main", "train", "map", {"key": "text", "prefix": "PRE:"})
    assert result["transformed"]


def test_dataset_validate_ok():
    from hf_services import DatasetManager
    dm = DatasetManager(backend="mock")
    dm.load("ORG/test-ds", split="train", pii_checked=True, contamination_checked=True)
    result = dm.validate_for_training("ORG/test-ds", "main", "train")
    assert result["valid"]


def test_dataset_validate_fails_pii():
    from hf_services import DatasetManager
    dm = DatasetManager(backend="mock")
    dm.load("ORG/test-ds", split="train", pii_checked=False, contamination_checked=True)
    result = dm.validate_for_training("ORG/test-ds", "main", "train")
    assert not result["valid"]
    assert any("PII" in e for e in result["errors"])


# --- Trainer ---
def test_trainer_train_mock():
    from hf_services import TrainerService, TrainingConfig
    ts = TrainerService(backend="mock")
    config = TrainingConfig(base_model="m", dataset_id="ds", dataset_revision="v1", output_dir="out", objective="test")
    result = ts.train(config)
    assert result["status"] == "completed"
    assert "eval_f1" in result["metrics"]


def test_trainer_blocked():
    from hf_services import TrainerService, TrainingConfig
    ts = TrainerService(backend="mock")
    config = TrainingConfig(base_model="m", dataset_id="ds", dataset_revision="v1", output_dir="out", objective="test")
    result = ts.train(config, approved=False)
    assert result["status"] == "blocked"


def test_trainer_list_jobs():
    from hf_services import TrainerService, TrainingConfig
    ts = TrainerService(backend="mock")
    config = TrainingConfig(base_model="m", dataset_id="ds", dataset_revision="v1", output_dir="out", objective="test")
    ts.train(config)
    jobs = ts.list_jobs()
    assert len(jobs) >= 1


# --- PEFT ---
def test_peft_create():
    from hf_services import PEFTService, PEFTConfig
    svc = PEFTService(backend="mock")
    config = PEFTConfig(base_model="m", adapter_name="lora1")
    result = svc.create_adapter(config)
    assert result["status"] == "created"
    assert result["trainable_percent"] < 5.0  # LoRA entrena < 5%


def test_peft_list():
    from hf_services import PEFTService, PEFTConfig
    svc = PEFTService(backend="mock")
    svc.create_adapter(PEFTConfig(base_model="m", adapter_name="a1"))
    svc.create_adapter(PEFTConfig(base_model="m", adapter_name="a2"))
    assert len(svc.list_adapters()) == 2


def test_peft_save():
    from hf_services import PEFTService, PEFTConfig
    svc = PEFTService(backend="mock")
    result = svc.create_adapter(PEFTConfig(base_model="m", adapter_name="a1"))
    save = svc.save_adapter(result["adapter_id"], "ORG/my-adapter")
    assert save["saved"]


# --- Evaluate ---
def test_evaluate_accuracy():
    from hf_services import EvaluateService
    ev = EvaluateService(backend="mock")
    result = ev.compute("accuracy", [0, 1, 2, 3], [0, 1, 2, 3])
    assert result["result"]["accuracy"] == 1.0


def test_evaluate_partial():
    from hf_services import EvaluateService
    ev = EvaluateService(backend="mock")
    result = ev.compute("accuracy", [0, 1, 2, 3], [0, 1, 2, 0])
    assert result["result"]["accuracy"] == 0.75


def test_evaluate_compare():
    from hf_services import EvaluateService
    ev = EvaluateService(backend="mock")
    result = ev.compare("accuracy", {
        "model_a": ([0, 1, 2], [0, 1, 2]),
        "model_b": ([0, 1, 0], [0, 1, 2]),
    })
    assert result["best_model"] == "model_a"


def test_evaluate_length_mismatch():
    from hf_services import EvaluateService
    ev = EvaluateService(backend="mock")
    result = ev.compute("accuracy", [0, 1], [0])
    assert "error" in result


# --- Spaces ---
def test_space_create():
    from hf_services import SpaceManager, SpaceStatus
    mgr = SpaceManager(backend="mock")
    space = mgr.create(name="test-space", sdk="gradio", model_id="m")
    assert space.status == SpaceStatus.RUNNING
    assert space.url


def test_space_list():
    from hf_services import SpaceManager
    mgr = SpaceManager(backend="mock")
    mgr.create(name="s1", sdk="gradio")
    mgr.create(name="s2", sdk="docker")
    assert len(mgr.list_spaces()) == 2


def test_space_stop():
    from hf_services import SpaceManager, SpaceStatus
    mgr = SpaceManager(backend="mock")
    space = mgr.create(name="test", sdk="gradio")
    result = mgr.stop(space.space_id)
    assert result["stopped"]
    assert mgr.get(space.space_id).status == SpaceStatus.STOPPED


def test_space_delete():
    from hf_services import SpaceManager
    mgr = SpaceManager(backend="mock")
    space = mgr.create(name="test", sdk="gradio")
    result = mgr.delete(space.space_id)
    assert result["deleted"]


# --- Model Cards ---
def test_model_card_create():
    from hf_services import ModelCardService, ModelCardData
    svc = ModelCardService(backend="mock")
    card = svc.create(ModelCardData(model_id="test/v1", license="MIT", intended_use="Testing"))
    assert card.model_id == "test/v1"
    assert card.license == "MIT"


def test_model_card_markdown():
    from hf_services import ModelCardService, ModelCardData
    svc = ModelCardService(backend="mock")
    svc.create(ModelCardData(model_id="test/v1", base_model="base", license="MIT", intended_use="Testing"))
    md = svc.get_markdown("test/v1")
    assert "test/v1" in md
    assert "MIT" in md
    assert "Testing" in md


def test_model_card_approve():
    from hf_services import ModelCardService, ModelCardData
    svc = ModelCardService(backend="mock")
    svc.create(ModelCardData(model_id="test/v1"))
    result = svc.approve("test/v1", approved_by="admin", red_team_passed=True)
    assert result["approved"]


def test_model_card_approve_red_team_fails():
    from hf_services import ModelCardService, ModelCardData
    svc = ModelCardService(backend="mock")
    svc.create(ModelCardData(model_id="test/v1"))
    result = svc.approve("test/v1", approved_by="admin", red_team_passed=False)
    assert not result["approved"]


def test_model_card_push_without_approval():
    from hf_services import ModelCardService, ModelCardData
    svc = ModelCardService(backend="mock")
    svc.create(ModelCardData(model_id="test/v1"))
    result = svc.push_to_hub("test/v1", "ORG/repo")
    assert not result["pushed"]


def test_model_card_push_with_approval():
    from hf_services import ModelCardService, ModelCardData
    svc = ModelCardService(backend="mock")
    svc.create(ModelCardData(model_id="test/v1"))
    svc.approve("test/v1", approved_by="admin", red_team_passed=True)
    result = svc.push_to_hub("test/v1", "ORG/repo")
    assert result["pushed"]


def test_model_card_list():
    from hf_services import ModelCardService, ModelCardData
    svc = ModelCardService(backend="mock")
    svc.create(ModelCardData(model_id="m1"))
    svc.create(ModelCardData(model_id="m2"))
    assert len(svc.list_cards()) == 2


# --- Orchestrator integration ---
def test_orch_hf_status():
    from orchestrator import UC320Orchestrator
    orch = UC320Orchestrator()
    status = orch.hf_status()
    assert "services" in status


def test_orch_create_endpoint():
    from orchestrator import UC320Orchestrator
    orch = UC320Orchestrator()
    result = orch.create_endpoint(name="test", model_id="mock/sentiment-mock")
    assert result["allowed"]
    assert "endpoint" in result


def test_orch_load_dataset():
    from orchestrator import UC320Orchestrator
    orch = UC320Orchestrator()
    result = orch.load_dataset("ORG/test", pii_checked=True, contamination_checked=True)
    assert result["allowed"]


def test_orch_train_model():
    from orchestrator import UC320Orchestrator
    from hf_services import TrainingConfig
    orch = UC320Orchestrator()
    config = TrainingConfig(base_model="mock/sentiment-mock", dataset_id="ds", dataset_revision="v1", output_dir="out", objective="test")
    result = orch.train_model(config)
    assert result["allowed"]
    assert result["status"] == "completed"


def test_orch_create_peft():
    from orchestrator import UC320Orchestrator
    from hf_services import PEFTConfig
    orch = UC320Orchestrator()
    result = orch.create_peft_adapter(PEFTConfig(base_model="mock/sentiment-mock", adapter_name="lora1"))
    assert result["allowed"]


def test_orch_compute_metrics():
    from orchestrator import UC320Orchestrator
    orch = UC320Orchestrator()
    result = orch.compute_metrics("accuracy", [0, 1], [0, 1])
    assert result["result"]["accuracy"] == 1.0


def test_orch_create_space():
    from orchestrator import UC320Orchestrator
    orch = UC320Orchestrator()
    result = orch.create_space(name="test", sdk="gradio", model_id="mock/sentiment-mock")
    assert result["allowed"]


def test_orch_model_card():
    from orchestrator import UC320Orchestrator
    from hf_services import ModelCardData
    orch = UC320Orchestrator()
    card = orch.create_model_card(ModelCardData(model_id="test/v1", license="MIT"))
    assert card["created"]
    approval = orch.approve_model_card("test/v1", "admin", red_team_passed=True)
    assert approval["approved"]
