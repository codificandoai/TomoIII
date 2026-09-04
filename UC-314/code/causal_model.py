"""UC-314 — Modelo Causal Simbólico (SCM) y simulador de razonamiento LLM.

El SCM representa dependencias causales como un DAG. El LLM simulado genera
hipótesis lingüísticas que pueden validarse contra el grafo.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class CausalNode:
    name: str
    state: str = "OK"
    parents: List[str] = field(default_factory=list)
    children: List[str] = field(default_factory=list)


class SymbolicCausalModel:
    """Grafo Acíclico Dirigido (DAG) de dependencias causales."""

    def __init__(self) -> None:
        self.nodes: Dict[str, CausalNode] = {}
        self._cycle_cache: Optional[Set[str]] = None

    def add_dependency(self, parent: str, child: str) -> None:
        """Registra que `parent` es causa de `child`."""
        if parent not in self.nodes:
            self.nodes[parent] = CausalNode(name=parent)
        if child not in self.nodes:
            self.nodes[child] = CausalNode(name=child)
        if child not in self.nodes[parent].children:
            self.nodes[parent].children.append(child)
        if parent not in self.nodes[child].parents:
            self.nodes[child].parents.append(parent)
        self._cycle_cache = None

    def set_node_state(self, node: str, state: str) -> None:
        if node in self.nodes:
            self.nodes[node].state = state

    def get_state(self, node: str) -> str:
        return self.nodes.get(node, CausalNode(name=node)).state

    def _ancestors(self, node: str, seen: Optional[Set[str]] = None) -> Set[str]:
        seen = seen or set()
        if node in seen:
            return seen
        seen.add(node)
        for parent in self.nodes.get(node, CausalNode()).parents:
            self._ancestors(parent, seen)
        return seen

    def has_cycle(self) -> bool:
        """Detección de ciclos mediante DFS con colores."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = {n: WHITE for n in self.nodes}

        def dfs(node: str) -> bool:
            color[node] = GRAY
            for child in self.nodes[node].children:
                if child not in color:
                    continue
                if color[child] == GRAY:
                    return True
                if color[child] == WHITE and dfs(child):
                    return True
            color[node] = BLACK
            return False

        for node in list(self.nodes):
            if color[node] == WHITE and dfs(node):
                return True
        return False

    def find_symbolic_root_cause(self, failed_node: str) -> List[str]:
        """Traza hacia atrás encontrando el primer ancestro en estado FALLO."""
        if failed_node not in self.nodes:
            return [failed_node]
        trace: List[str] = [failed_node]
        queue: List[str] = [failed_node]
        visited: Set[str] = {failed_node}

        while queue:
            current = queue.pop(0)
            for parent in self.nodes[current].parents:
                if parent in visited:
                    continue
                visited.add(parent)
                trace.append(parent)
                if "FALLO" in self.nodes[parent].state or self.nodes[parent].state != "OK":
                    return trace
                queue.append(parent)
        return trace

    def check_plan_consistency(self, required_nodes: List[str]) -> Dict[str, Any]:
        """Verifica que los nodos requeridos por un plan estén en estado OK."""
        issues = []
        for node in required_nodes:
            state = self.get_state(node)
            if "FALLO" in state or state != "OK":
                issues.append({"node": node, "state": state})
        return {"consistent": not issues, "issues": issues}

    def to_dict(self) -> Dict[str, Any]:
        return {
            node: {"state": n.state, "parents": n.parents, "children": n.children}
            for node, n in self.nodes.items()
        }


class LLMReasoner:
    """Simulador de razonamiento de un LLM con tendencia a correlación."""

    @staticmethod
    def abstract_hypothesis(error_msg: str, context: str) -> Dict[str, Any]:
        time.sleep(0.05)  # simula latencia
        msg = error_msg.lower()
        if any(k in msg for k in ("conexion", "timeout", "network", "conexión")):
            return {
                "reasoning": "El error menciona timeout/conexión; es probable que el token de sesión haya expirado.",
                "proposed_root_cause": "TokenSession",
                "confidence": 0.85,
            }
        if "pricing" in msg or "precio" in msg:
            return {
                "reasoning": "La falla ocurrió en el servicio de precios; la causa raíz parece ser PricingAPI.",
                "proposed_root_cause": "PricingAPI",
                "confidence": 0.75,
            }
        if "api" in msg:
            return {
                "reasoning": "Error genérico de API; reintentar la operación puede resolverlo.",
                "proposed_root_cause": None,
                "confidence": 0.4,
            }
        return {
            "reasoning": "Error desconocido. Se recomienda reintentar o escalar a soporte humano.",
            "proposed_root_cause": None,
            "confidence": 0.1,
        }

    @staticmethod
    def decompose_goal(goal: str, available_tools: List[Dict[str, Any]]) -> List[str]:
        """Simula la descomposición de un objetivo en subtareas de alto nivel."""
        goal_lower = goal.lower()
        steps = []
        if any(k in goal_lower for k in ("campaña", "campaign", "marketing")):
            steps = [
                "Investigar el público objetivo de la campaña",
                "Redactar el texto del anuncio",
                "Diseñar el creativo del anuncio",
                "Seleccionar canales de distribución",
                "Lanzar la campaña",
            ]
        elif any(k in goal_lower for k in ("email", "correo", "notificar")):
            steps = ["Redactar el cuerpo del correo", "Enviar el correo electrónico"]
        elif any(k in goal_lower for k in ("audience", "público", "segmento")):
            steps = [f"Investigar el público objetivo para: {goal}"]
        elif any(k in goal_lower for k in ("creativo", "creative", "diseño")):
            steps = ["Redactar el texto del anuncio", "Diseñar el creativo del anuncio"]
        else:
            # Descomposición genérica: dividir por verbos comunes.
            steps = re.split(r";|\sy\s|,", goal)
            steps = [s.strip().capitalize() for s in steps if s.strip()]
            if not steps:
                steps = [goal]
        return steps

    @staticmethod
    def propose_tool_for_goal(goal: str, tools: List[Dict[str, Any]]) -> Optional[str]:
        goal_lower = goal.lower()
        for tool in tools:
            name = tool["name"].lower()
            purpose = tool["purpose"].lower()
            if name in goal_lower or any(token in purpose for token in goal_lower.split()):
                return tool["name"]
        return None
