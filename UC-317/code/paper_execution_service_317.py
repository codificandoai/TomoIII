"""
UC-317 — Paper execution service / adapter.

Provides a strict paper-only execution adapter that can be injected into
UC-308's ChampionChallengerExperiment. It never executes real orders, only
registers and delegates to duck-typed paper engines, enforces real_order=False,
returns cancel/reconciliation status and has no network/filesystem side effects.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional


class PaperExecutionService:
    """Minimal paper execution adapter with strict paper-only policy."""

    def __init__(self) -> None:
        self._engines: Dict[str, Any] = {}
        self._assumptions: Dict[str, Dict[str, Any]] = {}
        self._canceled: Dict[str, bool] = {}

    def _key(self, experiment_id: str, model_id: str, version: str) -> str:
        return f"{experiment_id}:{model_id}:{version}"

    def register_engine(
        self,
        experiment_id: str,
        model_id: str,
        version: str,
        engine: Any,
        assumptions: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Register a duck-typed paper engine for a model/version."""
        key = self._key(experiment_id, model_id, version)
        self._engines[key] = engine
        self._assumptions[key] = assumptions or {}
        self._canceled[key] = False
        return {
            "success": True,
            "registered": True,
            "engine_key": key,
            "paper_only": True,
        }

    def execute(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Execute one paper trade. Denies any real order."""
        if request.get("real_order", False):
            return {
                "success": False,
                "allowed": False,
                "mode": "paper_only",
                "reason": "real orders are not allowed in paper execution",
                "order": None,
                "fills": [],
                "snapshot": None,
            }

        experiment_id = request.get("experiment_id", "")
        model_id = request.get("model_id", "")
        version = request.get("version", "")
        key = self._key(experiment_id, model_id, version)

        if self._canceled.get(key, False):
            return {
                "success": False,
                "allowed": False,
                "mode": "paper_only",
                "reason": "engine has been canceled",
                "order": None,
                "fills": [],
                "snapshot": None,
            }

        engine = self._engines.get(key)
        if engine is None:
            return {
                "success": False,
                "allowed": False,
                "mode": "paper_only",
                "reason": f"no paper engine registered for {key}",
                "order": None,
                "fills": [],
                "snapshot": None,
            }

        process = getattr(engine, "process_event", None)
        if not callable(process):
            return {
                "success": False,
                "allowed": False,
                "mode": "paper_only",
                "reason": "engine has no process_event method",
                "order": None,
                "fills": [],
                "snapshot": None,
            }

        market_event = request.get("market_event")
        prediction = request.get("prediction")
        try:
            result = process(market_event, prediction)
        except Exception as exc:
            return {
                "success": False,
                "allowed": False,
                "mode": "paper_only",
                "reason": f"process_event failed: {exc}",
                "order": None,
                "fills": [],
                "snapshot": None,
            }

        return {
            "success": True,
            "allowed": True,
            "mode": "paper_only",
            "reason": "paper execution completed",
            "order": result.get("order"),
            "fills": result.get("fills", []),
            "snapshot": result.get("snapshot"),
            "assumptions": self._assumptions.get(key, {}),
        }

    def cancel_all(
        self,
        experiment_id: str,
        model_id: str,
        version: str,
    ) -> Dict[str, Any]:
        """Cancel all pending paper orders for a registered engine."""
        key = self._key(experiment_id, model_id, version)
        self._canceled[key] = True
        engine = self._engines.get(key)
        canceled = []
        if engine is not None:
            cancel_fn = getattr(engine, "cancel_all_orders", None)
            if callable(cancel_fn):
                canceled = [o.to_dict() if hasattr(o, "to_dict") else o for o in cancel_fn()]
        return {
            "success": True,
            "engine_key": key,
            "canceled_orders": len(canceled),
            "canceled_order_ids": [o.get("order_id") for o in canceled],
        }

    def reconcile(
        self,
        experiment_id: str,
        model_id: str,
        version: str,
    ) -> Dict[str, Any]:
        """Return current paper portfolio reconciliation."""
        key = self._key(experiment_id, model_id, version)
        engine = self._engines.get(key)
        if engine is None:
            return {
                "success": False,
                "engine_key": key,
                "reason": "engine not found",
            }
        snap = getattr(engine, "snapshot", None)
        if callable(snap):
            snap = snap()
        elif hasattr(snap, "to_dict"):
            snap = snap.to_dict()
        return {
            "success": True,
            "engine_key": key,
            "snapshot": snap if isinstance(snap, dict) else (snap.to_dict() if hasattr(snap, "to_dict") else {}),
        }

    def status(self, experiment_id: str, model_id: str, version: str) -> Dict[str, Any]:
        key = self._key(experiment_id, model_id, version)
        return {
            "engine_key": key,
            "registered": key in self._engines,
            "canceled": self._canceled.get(key, False),
            "assumptions": self._assumptions.get(key, {}),
        }


def build_default_paper_execution_service() -> PaperExecutionService:
    """Factory for an empty, safe paper execution service."""
    return PaperExecutionService()
