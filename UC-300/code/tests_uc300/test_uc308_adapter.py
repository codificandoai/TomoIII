"""UC-300 adapter tests for UC-308 Champion/Challenger experiment guard."""

import pytest

from secure_tool_gateway import SecureToolGateway
from models_300 import GatewayConfig


@pytest.fixture
def gateway():
    config = GatewayConfig(
        token_secret="test-secret-32-bytes-long-12345678901234567890",
        token_ttl_seconds=300.0,
        rate_limit_per_minute=100,
        budget_daily=1000000.0,
    )
    return SecureToolGateway(config=config)


def test_authorize_experiment_trade_paper_only_for_challenger(gateway):
    result = gateway.authorize_experiment_trade({
        "experiment_id": "exp-1",
        "model_id": "challenger",
        "model_version": "2.0.0",
        "model_role": "challenger",
        "experiment_state": "paper",
        "real_order": False,
    })
    assert result["allowed"]
    assert result["mode"] == "paper_only"


def test_authorize_experiment_trade_denies_challenger_real_order(gateway):
    result = gateway.authorize_experiment_trade({
        "experiment_id": "exp-1",
        "model_id": "challenger",
        "model_version": "2.0.0",
        "model_role": "challenger",
        "experiment_state": "paper",
        "real_order": True,
    })
    assert not result["allowed"]
    assert "real order denied" in result["reason"]


def test_authorize_experiment_trade_allows_promoted_champion_real_order(gateway):
    result = gateway.authorize_experiment_trade({
        "experiment_id": "exp-1",
        "model_id": "champion",
        "model_version": "1.0.0",
        "model_role": "champion",
        "experiment_state": "promoted",
        "real_order": True,
        "expected_model_id": "champion",
        "expected_version": "1.0.0",
    })
    assert result["allowed"]


def test_authorize_experiment_trade_binding_mismatch(gateway):
    result = gateway.authorize_experiment_trade({
        "experiment_id": "exp-1",
        "model_id": "champion",
        "model_version": "1.0.0",
        "model_role": "champion",
        "experiment_state": "promoted",
        "real_order": True,
        "expected_model_id": "other",
        "expected_version": "1.0.0",
    })
    assert not result["allowed"]
    assert "model_id binding mismatch" in result["reason"]


def test_authorize_experiment_trade_requires_binding(gateway):
    result = gateway.authorize_experiment_trade({
        "experiment_id": "exp-1",
        "model_id": "",
        "model_version": "1.0.0",
        "model_role": "champion",
        "experiment_state": "promoted",
        "real_order": False,
    })
    assert not result["allowed"]
    assert "missing" in result["reason"]
