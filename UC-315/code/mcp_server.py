"""Registro MCP dinámico de herramientas de trading para UC-292."""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from models import ToolDefinition


class MCPToolServer:
    """Registro de herramientas con JSON Schema y niveles de riesgo."""

    def __init__(self) -> None:
        self._tools: Dict[str, tuple[ToolDefinition, Callable[[dict], Any]]] = {}

    def register(
        self,
        definition: ToolDefinition,
        handler: Callable[[dict], Any],
    ) -> None:
        if definition.name in self._tools:
            raise ValueError(f"tool already registered: {definition.name}")
        self._tools[definition.name] = (definition, handler)

    def list_tools(self) -> List[dict]:
        return [
            {
                "name": d.name,
                "description": d.description,
                "inputSchema": d.input_schema,
                "risk": d.risk,
            }
            for d, _ in self._tools.values()
        ]

    def call_tool(
        self,
        name: str,
        arguments: dict,
        approved: bool = False,
    ) -> dict:
        if name not in self._tools:
            raise KeyError(f"tool not found: {name}")
        definition, handler = self._tools[name]
        self._validate(definition.input_schema, arguments)
        if definition.risk == "dangerous" and not approved:
            return {"status": "approval_required", "tool": name}
        return {"status": "ok", "tool": name, "content": handler(arguments)}

    @staticmethod
    def _validate(schema: dict, arguments: dict) -> None:
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        missing = [key for key in required if key not in arguments]
        if missing:
            raise ValueError(f"missing tool arguments: {missing}")
        extra = [key for key in arguments if key not in properties]
        if extra:
            raise ValueError(f"unknown tool arguments: {extra}")
        types = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        for key, value in arguments.items():
            expected = types.get(properties[key].get("type"))
            if expected and not isinstance(value, expected):
                # bool es subclass de int, tratar separadamente
                if expected == int and isinstance(value, bool):
                    raise ValueError(f"invalid type for {key}")
                raise ValueError(f"invalid type for {key}")
            if "enum" in properties[key] and value not in properties[key]["enum"]:
                raise ValueError(f"invalid value for {key}")


def build_trading_mcp_server(
    perception_provider: Callable[[dict], Any],
    analysis_provider: Callable[[dict], Any],
    risk_provider: Callable[[dict], Any],
    juice_provider: Callable[[dict], Any],
    order_provider: Callable[[dict], Any],
    portfolio_provider: Callable[[], Any],
) -> MCPToolServer:
    server = MCPToolServer()

    server.register(
        ToolDefinition(
            name="get_market_snapshot",
            description="Obtiene snapshot de mercado procesado a partir de ticks y noticias.",
            input_schema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "ticks": {"type": "array"},
                    "news": {"type": "array"},
                },
                "required": ["symbol", "ticks"],
            },
        ),
        perception_provider,
    )

    server.register(
        ToolDefinition(
            name="run_technical_analysis",
            description="Devuelve indicadores técnicos para un conjunto de ticks.",
            input_schema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "ticks": {"type": "array"},
                },
                "required": ["symbol", "ticks"],
            },
        ),
        analysis_provider,
    )

    server.register(
        ToolDefinition(
            name="run_risk_assessment",
            description="Evalúa riesgo de una señal contra portafolio y restricciones.",
            input_schema={
                "type": "object",
                "properties": {
                    "signal": {"type": "object"},
                    "portfolio": {"type": "object"},
                    "constraints": {"type": "object"},
                },
                "required": ["signal", "portfolio"],
            },
        ),
        risk_provider,
    )

    server.register(
        ToolDefinition(
            name="validate_with_juice_agents",
            description="Solicita validación de una inferencia a los Juice Agents.",
            input_schema={
                "type": "object",
                "properties": {
                    "signal": {"type": "object"},
                    "snapshot": {"type": "object"},
                },
                "required": ["signal", "snapshot"],
            },
        ),
        juice_provider,
    )

    server.register(
        ToolDefinition(
            name="submit_order",
            description="Envía una orden al exchange simulado (acción peligrosa).",
            input_schema={
                "type": "object",
                "properties": {
                    "action": {"type": "object"},
                    "portfolio": {"type": "object"},
                    "price": {"type": "number"},
                },
                "required": ["action", "portfolio"],
            },
            risk="dangerous",
        ),
        order_provider,
    )

    server.register(
        ToolDefinition(
            name="get_portfolio",
            description="Devuelve el estado actual del portafolio.",
            input_schema={
                "type": "object",
                "properties": {},
            },
        ),
        lambda args: portfolio_provider(),
    )

    return server
