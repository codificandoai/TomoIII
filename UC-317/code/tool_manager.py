"""UC-317 — Tool Manager: registro, validación y ejecución de herramientas."""
from __future__ import annotations

import json
import math
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class Tool:
    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    required: List[str] = field(default_factory=list)
    handler: Optional[Callable[..., Any]] = None

    def to_openai(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {"type": "object", "properties": self.parameters, "required": self.required},
            },
        }

    def validate_args(self, args: Dict[str, Any]) -> List[str]:
        errors = []
        for req in self.required:
            if req not in args:
                errors.append(f"missing required parameter: {req}")
        return errors

    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        if self.handler is None:
            return {"error": f"Tool {self.name} has no handler"}
        errors = self.validate_args(args)
        if errors:
            return {"error": errors}
        try:
            result = self.handler(**args)
            return {"success": True, "result": result}
        except Exception as exc:
            return {"success": False, "error": str(exc)}


class BaseTool(ABC):
    @abstractmethod
    def get_tool(self) -> Tool:
        ...


class CalculatorTool(BaseTool):
    def get_tool(self) -> Tool:
        return Tool(
            name="calculator",
            description="Evaluate a simple arithmetic expression",
            parameters={"expression": {"type": "string", "description": "Arithmetic expression"}},
            required=["expression"],
            handler=self._run,
        )

    def _run(self, expression: str) -> Any:
        allowed = set("0123456789+-*/().^ ")
        if any(c not in allowed for c in expression):
            raise ValueError("Unsafe characters in expression")
        expression = expression.replace("^", "**")
        return eval(expression, {"__builtins__": {}}, {"math": math})


class SearchTool(BaseTool):
    def get_tool(self) -> Tool:
        return Tool(
            name="search",
            description="Search for a keyword and return mock results",
            parameters={"query": {"type": "string"}},
            required=["query"],
            handler=self._run,
        )

    def _run(self, query: str) -> Any:
        return {"results": [f"result 1 for {query}", f"result 2 for {query}"]}


class WeatherTool(BaseTool):
    def get_tool(self) -> Tool:
        return Tool(
            name="weather",
            description="Return mock weather for a city",
            parameters={"city": {"type": "string"}},
            required=["city"],
            handler=self._run,
        )

    def _run(self, city: str) -> Any:
        return {"city": city, "temperature_c": 22, "condition": "sunny"}


class DateTool(BaseTool):
    def get_tool(self) -> Tool:
        return Tool(
            name="current_date",
            description="Return the current date",
            parameters={},
            required=[],
            handler=self._run,
        )

    def _run(self) -> Any:
        from datetime import datetime
        return {"date": datetime.now().isoformat()}


class ToolManager:
    """Registro de herramientas disponibles para los agentes."""

    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}
        self.register(CalculatorTool().get_tool())
        self.register(SearchTool().get_tool())
        self.register(WeatherTool().get_tool())
        self.register(DateTool().get_tool())

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def list_tools(self) -> List[Dict[str, Any]]:
        return [tool.to_openai()["function"] for tool in self._tools.values()]

    def get_tool(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def call(self, name: str, args: Any) -> Dict[str, Any]:
        tool = self.get_tool(name)
        if not tool:
            return {"success": False, "error": f"Tool {name} not found"}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                return {"success": False, "error": f"Invalid JSON arguments for {name}"}
        return tool.execute(args)
