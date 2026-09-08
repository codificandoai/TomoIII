"""
Fixtures compartidas para tests de UC-300.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models_300 import GatewayConfig, ToolRequest
from secure_tool_gateway import SecureToolGateway


@pytest.fixture
def gateway():
    """Gateway con configuración determinista para tests."""
    config = GatewayConfig(
        token_secret="test-secret-32-bytes-long-12345678901234567890",
        token_ttl_seconds=300.0,
        rate_limit_per_minute=100,
        budget_daily=1000000.0,
    )
    return SecureToolGateway(config=config)


@pytest.fixture
def low_risk_update_request():
    return ToolRequest(
        agent_id="agent_pricing_eu",
        action="update_price",
        params={"product_id": "SKU-001", "new_price": 120.5, "reason": "Ajuste mensual"},
        environment="default",
    )


@pytest.fixture
def high_risk_payment_request():
    return ToolRequest(
        agent_id="agent_pricing_us",
        action="send_payment",
        params={"recipient_id": "vendor_1", "amount": 15000.0, "currency": "USD", "memo": "Factura"},
        environment="default",
    )


@pytest.fixture
def destructive_delete_request():
    return ToolRequest(
        agent_id="agent_pricing_eu",
        action="delete_product",
        params={"product_id": "SKU-001", "confirmation_code": "CONFIRM-ABCD"},
        environment="default",
    )


@pytest.fixture
def safe_read_request():
    return ToolRequest(
        agent_id="agent_reader",
        action="read_file",
        params={"path": "catalog/eu_products.md"},
        environment="default",
    )
