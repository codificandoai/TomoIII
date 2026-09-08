"""
UC-300 — Ejecutor sandbox simulado.

No ejecuta comandos, filesystem, pagos ni APIs reales. Todas las
herramientas son handlers allowlisted que devuelven resultados simulados.
Las operaciones destructivas se ejecutan como dry-run.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Callable, Dict, List, Optional

from models_300 import ExecutionResult, ExecutionStatus


Handler = Callable[[str, str, Dict[str, Any]], ExecutionResult]


class SimulatedState:
    """Estado simulado para el sandbox."""

    def __init__(self):
        self.products = {
            "SKU-001": {"price": 99.99, "region": "EU"},
            "SKU-002": {"price": 149.99, "region": "EU"},
            "SKU-100": {"price": 79.99, "region": "US"},
            "SKU-101": {"price": 199.99, "region": "US"},
        }
        self.payments_today = 0.0
        self.files = {
            "catalog/eu_products.md": "# EU Catalog\n- SKU-001\n- SKU-002",
            "catalog/us_products.md": "# US Catalog\n- SKU-100\n- SKU-101",
            "docs/price_policy.md": "# Price Policy\nMax variation 10%",
        }


class SandboxExecutor:
    """Ejecutor de herramientas en sandbox simulado."""

    def __init__(self, state: Optional[SimulatedState] = None):
        self._state = state or SimulatedState()
        self._handlers: Dict[str, Handler] = {
            "update_price": self._handle_update_price,
            "delete_product": self._handle_delete_product,
            "send_payment": self._handle_send_payment,
            "read_file": self._handle_read_file,
        }

    def is_registered(self, action: str) -> bool:
        return action in self._handlers

    def execute(
        self,
        trace_id: str,
        agent_id: str,
        action: str,
        params: Dict[str, Any],
        dry_run: bool = False,
    ) -> ExecutionResult:
        handler = self._handlers.get(action)
        if handler is None:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE,
                action=action,
                agent_id=agent_id,
                trace_id=trace_id,
                error=f"tool '{action}' not registered in sandbox",
                dry_run=dry_run,
            )

        # El handler recibe (trace_id, agent_id, params)
        result = handler(trace_id, agent_id, params)
        result.dry_run = dry_run
        return result

    def validate_output(
        self,
        action: str,
        output: Any,
    ) -> Dict[str, Any]:
        """Validación simple de la salida del sandbox."""
        if output is None:
            return {"valid": False, "reason": "output is null"}
        if action in ("update_price", "delete_product", "send_payment"):
            if not isinstance(output, dict):
                return {"valid": False, "reason": "output must be a dict"}
            if "success" not in output:
                return {"valid": False, "reason": "output missing success field"}
        if action == "read_file":
            if not isinstance(output, dict):
                return {"valid": False, "reason": "read_file output must be a dict"}
            if "content" not in output:
                return {"valid": False, "reason": "read_file output missing content"}
        return {"valid": True, "reason": "ok"}

    def _handle_update_price(self, trace_id: str, agent_id: str, params: Dict[str, Any]) -> ExecutionResult:
        product_id = params.get("product_id")
        new_price = float(params.get("new_price", 0))
        reason = params.get("reason", "")
        old_price = self._state.products.get(product_id, {}).get("price")
        if old_price is None:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE,
                action="update_price",
                agent_id=agent_id,
                trace_id=trace_id,
                output={"success": False, "error": "product not found"},
            )
        # Simular actualización
        self._state.products[product_id]["price"] = new_price
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            action="update_price",
            agent_id=agent_id,
            trace_id=trace_id,
            output={
                "success": True,
                "product_id": product_id,
                "old_price": old_price,
                "new_price": new_price,
                "reason": reason,
                "simulated": True,
            },
        )

    def _handle_delete_product(self, trace_id: str, agent_id: str, params: Dict[str, Any]) -> ExecutionResult:
        product_id = params.get("product_id")
        confirmation_code = params.get("confirmation_code")
        hard_delete = params.get("hard_delete", False)
        if product_id not in self._state.products:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE,
                action="delete_product",
                agent_id=agent_id,
                trace_id=trace_id,
                output={"success": False, "error": "product not found"},
            )
        if not re.match(r"^CONFIRM-[A-Z]{4}$", str(confirmation_code).upper()):
            return ExecutionResult(
                status=ExecutionStatus.FAILURE,
                action="delete_product",
                agent_id=agent_id,
                trace_id=trace_id,
                output={"success": False, "error": "invalid confirmation code"},
            )
        # Operación destructiva: dry-run; no eliminamos realmente del estado
        deleted = self._state.products.get(product_id)
        return ExecutionResult(
            status=ExecutionStatus.DRY_RUN,
            action="delete_product",
            agent_id=agent_id,
            trace_id=trace_id,
            output={
                "success": True,
                "dry_run": True,
                "product_id": product_id,
                "would_delete": dict(deleted) if deleted else None,
                "hard_delete": hard_delete,
                "confirmation_code_prefix": confirmation_code[:8] if confirmation_code else "",
                "simulated": True,
            },
        )

    def _handle_send_payment(self, trace_id: str, agent_id: str, params: Dict[str, Any]) -> ExecutionResult:
        recipient_id = params.get("recipient_id")
        amount = float(params.get("amount", 0))
        currency = params.get("currency", "USD")
        memo = params.get("memo", "")
        # Simulación de pago; nunca se toca API real
        return ExecutionResult(
            status=ExecutionStatus.DRY_RUN,
            action="send_payment",
            agent_id=agent_id,
            trace_id=trace_id,
            output={
                "success": True,
                "dry_run": True,
                "recipient_id": recipient_id,
                "amount": amount,
                "currency": currency,
                "memo": memo,
                "transaction_id": f"SIM-{trace_id[:8]}-{agent_id[:8]}",
                "simulated": True,
            },
        )

    def _handle_read_file(self, trace_id: str, agent_id: str, params: Dict[str, Any]) -> ExecutionResult:
        path = params.get("path", "")
        content = self._state.files.get(path)
        if content is None:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE,
                action="read_file",
                agent_id=agent_id,
                trace_id=trace_id,
                output={"success": False, "error": "file not found in simulated filesystem"},
            )
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            action="read_file",
            agent_id=agent_id,
            trace_id=trace_id,
            output={
                "success": True,
                "path": path,
                "content": content,
                "simulated": True,
            },
        )

    def get_state_snapshot(self) -> Dict[str, Any]:
        return {
            "products": copy.deepcopy(self._state.products),
            "files": copy.deepcopy(self._state.files),
            "payments_today": self._state.payments_today,
        }

    def reset_state(self) -> None:
        self._state = SimulatedState()
