"""UC-314 — Planificador recursivo con verificación causal.

El planificador recibe un objetivo de alto nivel, lo descompone en subtareas
mediante un razonador simulado (LLM) y verifica cada paso contra un Modelo
Causal Simbólico. Cada paso es una hoja ejecutable (existe una herramienta) o
una rama que se expande recursivamente hasta alcanzar la condición de parada.
"""
from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from causal_model import LLMReasoner, SymbolicCausalModel
from tool_registry import ToolRegistry


@dataclass
class PlanNode:
    id: str
    goal: str
    depth: int = 0
    tool_name: Optional[str] = None
    tool_inputs: Dict[str, Any] = field(default_factory=dict)
    causal_dependencies: List[str] = field(default_factory=list)
    children: List["PlanNode"] = field(default_factory=list)
    status: str = "pending"  # pending | executable | blocked | executed | failed
    reasoning: str = ""
    execution_result: Optional[Dict[str, Any]] = None
    audit: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "goal": self.goal,
            "depth": self.depth,
            "tool_name": self.tool_name,
            "tool_inputs": self.tool_inputs,
            "causal_dependencies": self.causal_dependencies,
            "status": self.status,
            "reasoning": self.reasoning,
            "execution_result": self.execution_result,
            "audit": self.audit,
            "children": [c.to_dict() for c in self.children],
        }


class RecursivePlanner:
    """Descompone un objetivo en un árbol de acciones ejecutables.

    Condiciones de parada:
      - La subtarea coincide directamente con una herramienta registrada.
      - Se alcanza la profundidad máxima.
      - Se alcanza el número máximo de nodos.
      - El SCM detecta una dependencia causal en fallo.
      - El razonador no logra descomponer más la subtarea.
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        causal_model: Optional[SymbolicCausalModel] = None,
        max_depth: int = 5,
        max_nodes: int = 100,
        llm: Optional[LLMReasoner] = None,
    ) -> None:
        self.registry = tool_registry
        self.causal_model = causal_model or SymbolicCausalModel()
        self.llm = llm or LLMReasoner()
        self.max_depth = max_depth
        self.max_nodes = max_nodes
        self._node_count = 0
        self._start_time = 0.0

    def plan(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> PlanNode:
        """Genera el plan recursivo para el objetivo dado."""
        self._node_count = 0
        self._start_time = time.time()
        root = PlanNode(id=str(uuid.uuid4())[:8], goal=goal, depth=0)
        self._expand(root)
        return root

    def _expand(self, node: PlanNode) -> None:
        self._node_count += 1
        if self._node_count > self.max_nodes:
            node.status = "blocked"
            node.reasoning = f"Límite de nodos ({self.max_nodes}) alcanzado."
            node.audit["stop_reason"] = "max_nodes"
            return
        if node.depth >= self.max_depth:
            node.status = "blocked"
            node.reasoning = f"Profundidad máxima ({self.max_depth}) alcanzada."
            node.audit["stop_reason"] = "max_depth"
            return

        # Verificación causal previa
        causal_check = self.causal_model.check_plan_consistency(node.causal_dependencies)
        if not causal_check["consistent"]:
            node.status = "blocked"
            node.reasoning = "Dependencia causal en fallo: " + str(causal_check["issues"])
            node.audit["stop_reason"] = "causal_dependency_failure"
            node.audit["causal_issues"] = causal_check["issues"]
            return

        # ¿Es una hoja ejecutable?
        tool = self.registry.find_matching_tool(node.goal)
        if tool:
            node.tool_name = tool.name
            node.status = "executable"
            node.reasoning = f"Herramienta directa encontrada: {tool.name}"
            node.audit["stop_reason"] = "direct_tool_match"
            # Inferir entradas simuladas a partir del contexto
            node.tool_inputs = self._infer_inputs(tool, node.goal)
            return

        # Descomponer
        subgoals = self.llm.decompose_goal(node.goal, self.registry.list_tools())
        if not subgoals or len(subgoals) == 1 and subgoals[0] == node.goal:
            node.status = "blocked"
            node.reasoning = "No se pudo descomponer más la subtarea."
            node.audit["stop_reason"] = "no_decomposition"
            return

        for sub in subgoals:
            child = PlanNode(
                id=str(uuid.uuid4())[:8],
                goal=sub,
                depth=node.depth + 1,
                causal_dependencies=self._infer_causal_dependencies(sub),
            )
            node.children.append(child)
            self._expand(child)

        # Estado del nodo padre depende de los hijos
        if all(c.status == "executable" for c in node.children):
            node.status = "executable"
        elif any(c.status == "blocked" for c in node.children):
            node.status = "blocked"
        else:
            node.status = "pending"
        node.audit["elapsed_ms"] = round((time.time() - self._start_time) * 1000, 2)

    @staticmethod
    def _infer_inputs(tool, goal: str) -> Dict[str, Any]:
        """Extrae valores simples del objetivo para los parámetros de la herramienta."""
        inputs: Dict[str, Any] = {}
        for param in tool.parameters:
            if "campaign" in goal.lower() and param.name == "campaign_goal":
                inputs[param.name] = goal
            elif "audience" in goal.lower() and param.name == "audience":
                inputs[param.name] = re.sub(r".*audiencia objetivo", "", goal, flags=re.I).strip(" :;")
            elif "copy" in goal.lower() or "texto" in goal.lower():
                if param.name == "tone":
                    inputs[param.name] = "professional"
            elif param.name == "to":
                inputs[param.name] = "stakeholder@example.com"
            elif param.name == "subject":
                inputs[param.name] = f"Asunto: {goal[:30]}"
            elif param.name == "body":
                inputs[param.name] = goal
        return inputs

    def _infer_causal_dependencies(self, goal: str) -> List[str]:
        """Mapea objetivos a nodos causales relevantes para validación."""
        deps = []
        goal_lower = goal.lower()
        if any(k in goal_lower for k in ("api", "pricing", "precio", "token")):
            deps.append("TokenSession")
            deps.append("PricingAPI")
        if any(k in goal_lower for k in ("campaña", "campaign", "email", "enviar")):
            deps.append("MarketingService")
        return deps

    def execute_plan(self, node: PlanNode) -> PlanNode:
        """Ejecuta recursivamente el plan simulando cada herramienta."""
        if node.tool_name:
            node.execution_result = self.registry.execute(node.tool_name, node.tool_inputs)
            node.status = "executed" if node.execution_result.get("success") else "failed"
            return node
        for child in node.children:
            self.execute_plan(child)
        node.status = "executed" if all(c.status == "executed" for c in node.children) else "failed"
        return node

    def reset_counters(self) -> None:
        self._node_count = 0
