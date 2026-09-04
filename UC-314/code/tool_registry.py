"""UC-314 — Registro de herramientas simuladas para planificación recursiva.

Cada herramienta describe su propósito, parámetros de entrada y una función de
ejecución simulada. El registry permite verificar si una subtarea es ejecutable
y ejecutarla si aplica.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set


@dataclass
class ToolParameter:
    name: str
    type: str = "string"
    description: str = ""
    required: bool = True


@dataclass
class Tool:
    name: str
    purpose: str
    parameters: List[ToolParameter] = field(default_factory=list)
    expected_output: str = ""
    executor: Optional[Callable[[Dict[str, Any]], Any]] = None
    keywords: Set[str] = field(default_factory=set)

    def matches(self, goal: str) -> bool:
        """La herramienta coincide si el objetivo menciona su nombre o alguna keyword definida."""
        goal_lower = goal.lower()
        if self.name.lower() in goal_lower:
            return True
        if self.keywords and any(k in goal_lower for k in self.keywords):
            return True
        return False

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecuta la herramienta real o devuelve un resultado simulado."""
        if self.executor:
            return {"success": True, "output": self.executor(inputs)}
        return {"success": True, "output": f"simulated:{self.name}({json.dumps(inputs)})"}


class ToolRegistry:
    """Catálogo de herramientas disponibles para el planificador recursivo."""

    def __init__(self, tools: Optional[List[Tool]] = None) -> None:
        self.tools: Dict[str, Tool] = {}
        if tools:
            for tool in tools:
                self.register(tool)

    def register(self, tool: Tool) -> None:
        self.tools[tool.name] = tool

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": t.name,
                "purpose": t.purpose,
                "parameters": [
                    {"name": p.name, "type": p.type, "description": p.description, "required": p.required}
                    for p in t.parameters
                ],
                "expected_output": t.expected_output,
            }
            for t in self.tools.values()
        ]

    def get_tool(self, name: str) -> Optional[Tool]:
        return self.tools.get(name)

    def find_matching_tool(self, goal: str) -> Optional[Tool]:
        """Selecciona la herramienta con mayor coincidencia de keywords/nombre."""
        goal_lower = goal.lower()
        best_tool: Optional[Tool] = None
        best_score = 0
        for tool in self.tools.values():
            score = 0
            if tool.name.lower() in goal_lower:
                score += 10
            for kw in tool.keywords:
                if kw in goal_lower:
                    score += 1
            if score > best_score:
                best_score = score
                best_tool = tool
        return best_tool

    def can_execute(self, goal: str) -> bool:
        return self.find_matching_tool(goal) is not None

    def execute(self, name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        tool = self.tools.get(name)
        if not tool:
            return {"success": False, "error": f"Tool '{name}' not found"}
        try:
            return tool.execute(inputs)
        except Exception as exc:
            return {"success": False, "error": str(exc)}


def default_tools() -> List[Tool]:
    """Conjunto de herramientas de ejemplo para campañas de marketing y operaciones."""
    return [
        Tool(
            name="research_audience",
            purpose="Investigar el público objetivo de una campaña de marketing.",
            parameters=[ToolParameter("campaign_goal", "string", "Objetivo de la campaña.")],
            expected_output="Perfil de audiencia con segmentos y preferencias.",
            keywords={"investigar", "audiencia", "público", "segmento"},
        ),
        Tool(
            name="write_ad_copy",
            purpose="Redactar el texto de un anuncio para una campaña.",
            parameters=[
                ToolParameter("audience", "string", "Audiencia objetivo."),
                ToolParameter("tone", "string", "Tono del mensaje."),
            ],
            expected_output="Texto del anuncio listo para publicar.",
            keywords={"redactar", "texto", "anuncio", "copy"},
        ),
        Tool(
            name="design_creative",
            purpose="Diseñar el material creativo de un anuncio.",
            parameters=[ToolParameter("ad_copy", "string", "Texto del anuncio.")],
            expected_output="URL o descriptor del creativo.",
            keywords={"diseñar", "creativo", "banner", "imagen"},
        ),
        Tool(
            name="select_channels",
            purpose="Seleccionar los canales de distribución de una campaña.",
            parameters=[ToolParameter("audience", "string", "Audiencia objetivo.")],
            expected_output="Lista de canales recomendados.",
            keywords={"seleccionar", "canales", "distribución", "medios"},
        ),
        Tool(
            name="launch_campaign",
            purpose="Publicar y lanzar una campaña en los canales seleccionados.",
            parameters=[
                ToolParameter("creative", "string", "Descriptor del creativo."),
                ToolParameter("channels", "list", "Canales seleccionados."),
            ],
            expected_output="Confirmación de campaña lanzada.",
            keywords={"lanzar", "publicar", "campaña", "go live"},
        ),
        Tool(
            name="send_email",
            purpose="Enviar un correo electrónico.",
            parameters=[
                ToolParameter("to", "string", "Destinatario."),
                ToolParameter("subject", "string", "Asunto."),
                ToolParameter("body", "string", "Cuerpo del mensaje."),
            ],
            expected_output="Confirmación de envío.",
            keywords={"enviar", "correo", "email", "notificar"},
        ),
    ]
