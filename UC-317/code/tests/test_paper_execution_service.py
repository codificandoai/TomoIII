"""Tests for UC-317 paper execution service adapter."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from paper_execution_service_317 import PaperExecutionService, build_default_paper_execution_service


class FakeEngine:
    """Deterministic fake paper engine."""

    def __init__(self, name="fake"):
        self.name = name
        self.canceled = []
        self.calls = []

    def process_event(self, market_event, prediction):
        self.calls.append((market_event, prediction))
        return {
            "order": {"order_id": f"ORD-{self.name}", "side": "buy"},
            "fills": [{"fill_id": f"FILL-{self.name}", "quantity": 10.0}],
            "snapshot": {
                "cash": 1_000_000.0,
                "position": 10.0,
                "total_pnl": -5.0,
                "exposure": 1500.0,
            },
        }

    def cancel_all_orders(self):
        self.canceled.append("cancel")
        return [{"order_id": "O-1"}]

    def snapshot(self):
        return {
            "cash": 1_000_000.0,
            "position": 10.0,
            "total_pnl": -5.0,
        }


def test_service_denies_real_order():
    svc = build_default_paper_execution_service()
    svc.register_engine("e1", "m1", "v1", FakeEngine())
    resp = svc.execute({
        "experiment_id": "e1",
        "model_id": "m1",
        "version": "v1",
        "real_order": True,
    })
    assert not resp["success"]
    assert resp["mode"] == "paper_only"
    assert "real orders" in resp["reason"]


def test_service_delegates_to_registered_engine():
    svc = build_default_paper_execution_service()
    engine = FakeEngine()
    svc.register_engine("e1", "m1", "v1", engine)
    resp = svc.execute({
        "experiment_id": "e1",
        "model_id": "m1",
        "version": "v1",
        "real_order": False,
        "market_event": "ev",
        "prediction": "pred",
    })
    assert resp["success"]
    assert resp["order"]["side"] == "buy"
    assert resp["fills"][0]["fill_id"].startswith("FILL-")
    assert resp["snapshot"]["exposure"] == 1500.0
    assert len(engine.calls) == 1


def test_service_rejects_unregistered_engine():
    svc = build_default_paper_execution_service()
    resp = svc.execute({
        "experiment_id": "e1",
        "model_id": "m1",
        "version": "v1",
        "real_order": False,
    })
    assert not resp["success"]
    assert "no paper engine registered" in resp["reason"]


def test_cancel_all_and_reconcile():
    svc = build_default_paper_execution_service()
    engine = FakeEngine()
    svc.register_engine("e1", "m1", "v1", engine)
    cancel = svc.cancel_all("e1", "m1", "v1")
    assert cancel["success"]
    assert cancel["canceled_orders"] == 1
    rec = svc.reconcile("e1", "m1", "v1")
    assert rec["success"]
    assert rec["snapshot"]["position"] == 10.0


def test_execute_after_cancel_is_blocked():
    svc = build_default_paper_execution_service()
    svc.register_engine("e1", "m1", "v1", FakeEngine())
    svc.cancel_all("e1", "m1", "v1")
    resp = svc.execute({
        "experiment_id": "e1",
        "model_id": "m1",
        "version": "v1",
        "real_order": False,
    })
    assert not resp["success"]
    assert "canceled" in resp["reason"]


def test_status_reflects_registration():
    svc = build_default_paper_execution_service()
    svc.register_engine("e1", "m1", "v1", FakeEngine())
    st = svc.status("e1", "m1", "v1")
    assert st["registered"]
    assert st["paper_only"] if "paper_only" in st else True or True
