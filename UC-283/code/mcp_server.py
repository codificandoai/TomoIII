"""Dynamic MCP-style tool registry with schema validation and risk metadata."""
from __future__ import annotations

from typing import Any, Callable, Dict, List

from models import ToolDefinition


class MCPToolServer:
    def __init__(self) -> None:
        self._tools: Dict[str, tuple[ToolDefinition, Callable[[dict], Any]]] = {}

    def register(self, definition: ToolDefinition, handler: Callable[[dict], Any]) -> None:
        if definition.name in self._tools: raise ValueError(f"tool already registered: {definition.name}")
        self._tools[definition.name] = (definition, handler)

    def list_tools(self) -> List[dict]:
        return [{"name": d.name, "description": d.description,
                 "inputSchema": d.input_schema, "risk": d.risk} for d, _ in self._tools.values()]

    def call_tool(self, name: str, arguments: dict, approved: bool = False) -> dict:
        if name not in self._tools: raise KeyError(f"tool not found: {name}")
        definition, handler = self._tools[name]
        self._validate(definition.input_schema, arguments)
        if definition.risk == "dangerous" and not approved:
            return {"status": "approval_required", "tool": name}
        return {"status": "ok", "tool": name, "content": handler(arguments)}

    @staticmethod
    def _validate(schema: dict, arguments: dict) -> None:
        properties = schema.get("properties", {})
        missing = [key for key in schema.get("required", []) if key not in arguments]
        if missing: raise ValueError(f"missing tool arguments: {missing}")
        extra = [key for key in arguments if key not in properties]
        if extra: raise ValueError(f"unknown tool arguments: {extra}")
        types = {"string": str, "number": (int, float), "integer": int, "boolean": bool}
        for key, value in arguments.items():
            expected = types.get(properties[key].get("type"))
            if expected and (not isinstance(value, expected) or isinstance(value, bool) and expected != bool):
                raise ValueError(f"invalid type for {key}")
            if "enum" in properties[key] and value not in properties[key]["enum"]:
                raise ValueError(f"invalid value for {key}")


def build_pricing_server(context_provider: Callable[[], dict]) -> MCPToolServer:
    server = MCPToolServer()
    server.register(ToolDefinition("get_market_context", "Read authoritative pricing context",
        {"type": "object", "properties": {"product_id": {"type": "string"}}, "required": ["product_id"]}),
        lambda args: context_provider())
    server.register(ToolDefinition("run_pricing_challenge", "Evaluate proposed price against deterministic tests",
        {"type": "object", "properties": {"price": {"type": "number"}}, "required": ["price"]}),
        lambda args: {"tested_price": args["price"]})
    server.register(ToolDefinition("apply_price", "Apply price to production", {
        "type": "object", "properties": {"price": {"type": "number"}}, "required": ["price"]}, risk="dangerous"),
        lambda args: {"applied_price": args["price"]})
    return server