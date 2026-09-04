"""UC-313 — Bucle de aprendizaje impulsado por la curiosidad y adquisición de habilidades.

El agente recibe un conjunto básico de herramientas y una metaherramienta
"aprender nueva habilidad". Su objetivo principal no es resolver una tarea
específica, sino minimizar su propia incertidumbre.

Cuando el agente falla en un problema:
1. Se le indica: "Has fallado. Formula una hipótesis sobre una nueva herramienta
   que podría haberte ayudado a tener éxito".
2. El sistema genera una firma de función Python como hipótesis.
3. Un generador de código simulado (o LLM real en producción) produce el cuerpo.
4. Se registra la nueva herramienta y se vuelve a intentar.

Todo el proceso queda trazado y sometido a la capa de plasticidad para evaluar
si la nueva habilidad mejora el fitness.
"""
from __future__ import annotations

import importlib.util
import inspect
import textwrap
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from cognitive_evolution_layer import (
    ExecutionObservation,
    UC307CognitiveEvolutionLayer,
)


class SkillOutcome(str, Enum):
    SOLVED = "solved"
    FAILED = "failed"
    NEW_SKILL_GENERATED = "new_skill_generated"


@dataclass
class Tool:
    """Representación de una herramienta adquirida."""

    name: str
    signature: str
    code: str
    description: str = ""
    version: int = 1
    parent_skill: Optional[str] = None
    usage_count: int = 0
    success_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "signature": self.signature,
            "code": self.code,
            "description": self.description,
            "version": self.version,
            "parent_skill": self.parent_skill,
            "usage_count": self.usage_count,
            "success_count": self.success_count,
        }


@dataclass
class CuriosityAttempt:
    """Registro de un intento de resolución con posible generación de habilidad."""

    attempt_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    problem: str = ""
    initial_tools: List[str] = field(default_factory=list)
    outcome: SkillOutcome = SkillOutcome.FAILED
    generated_skill: Optional[Tool] = None
    final_answer: Any = None
    uncertainty_before: float = 1.0
    uncertainty_after: float = 1.0
    trace: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attempt_id": self.attempt_id,
            "problem": self.problem,
            "initial_tools": self.initial_tools,
            "outcome": self.outcome.value,
            "generated_skill": self.generated_skill.to_dict() if self.generated_skill else None,
            "final_answer": self.final_answer,
            "uncertainty_before": self.uncertainty_before,
            "uncertainty_after": self.uncertainty_after,
            "trace": self.trace,
        }


class FailureCuriosityTrigger:
    """Genera una hipótesis de nueva herramienta a partir de un fallo."""

    def hypothesize(self, problem: str, available_tools: List[str]) -> Dict[str, str]:
        # En producción: llamada a LLM con el problema y las herramientas actuales.
        # Aquí simulamos una hipótesis sensata basada en palabras clave.
        problem_lower = problem.lower()
        if "precio" in problem_lower or "costo" in problem_lower:
            name = "consultar_precio"
            signature = "def consultar_precio(sku: str) -> float:"
            description = "Consulta el precio actual de un SKU."
        elif "sentimiento" in problem_lower or "news" in problem_lower:
            name = "analizar_sentimiento"
            signature = "def analizar_sentimiento(textos: list[str]) -> dict:"
            description = "Analiza el sentimiento de una lista de textos."
        elif "tendencia" in problem_lower or "trend" in problem_lower:
            name = "detectar_tendencia"
            signature = "def detectar_tendencia(serie: list[float]) -> str:"
            description = "Detecta la tendencia de una serie numérica."
        elif "riesgo" in problem_lower or "riesgo" in problem_lower:
            name = "evaluar_riesgo"
            signature = "def evaluar_riesgo(portfolio: dict) -> float:"
            description = "Evalúa el riesgo de un portfolio."
        else:
            name = "herramienta_nueva"
            signature = "def herramienta_nueva(entrada: str) -> str:"
            description = "Herramienta genérica para resolver el problema."

        return {
            "name": name,
            "signature": signature,
            "description": description,
        }


class SimulatedCodeGenerator:
    """Simula la generación de código a partir de una firma."""

    def generate(self, hypothesis: Dict[str, str]) -> str:
        name = hypothesis["name"]
        signature = hypothesis["signature"]
        description = hypothesis["description"]
        body = f'    """{description}"""\n'
        if name == "consultar_precio":
            body += '    # Simulación: consulta externa\n    return 100.0\n'
        elif name == "analizar_sentimiento":
            body += '    # Simulación: análisis simple\n    return {"positivo": 0.6, "negativo": 0.2, "neutral": 0.2}\n'
        elif name == "detectar_tendencia":
            body += '    if len(serie) < 2:\n        return "neutral"\n    return "alcista" if serie[-1] > serie[0] else "bajista"\n'
        elif name == "evaluar_riesgo":
            body += '    # Simulación: riesgo como volatilidad simple\n    return 0.15\n'
        else:
            body += '    return f"Procesado: {entrada}"\n'
        return f"{signature}\n{body}"


class ToolRegistry:
    """Registro de herramientas adquiridas."""

    def __init__(self) -> None:
        self.tools: Dict[str, Tool] = {}
        self._compiled: Dict[str, Callable[..., Any]] = {}

    def register(self, tool: Tool) -> None:
        self.tools[tool.name] = tool
        self._compiled[tool.name] = self._compile(tool.code, tool.name)

    def _compile(self, code: str, name: str) -> Callable[..., Any]:
        module_code = compile(code, f"<tool_{name}>", "exec")
        namespace: Dict[str, Any] = {}
        exec(module_code, namespace)
        for obj in namespace.values():
            if callable(obj) and obj.__name__ == name:
                return obj
        raise RuntimeError(f"No se encontró la función {name} en el código generado.")

    def has(self, name: str) -> bool:
        return name in self.tools

    def call(self, name: str, *args: Any, **kwargs: Any) -> Any:
        tool = self.tools.get(name)
        if not tool:
            raise KeyError(f"Tool {name} not registered")
        tool.usage_count += 1
        fn = self._compiled[name]
        return fn(*args, **kwargs)

    def list_tools(self) -> List[str]:
        return list(self.tools.keys())


class CuriositySkillLoop:
    """Orquesta el aprendizaje por curiosidad."""

    def __init__(
        self,
        evolution_layer: Optional[UC307CognitiveEvolutionLayer] = None,
    ) -> None:
        self.registry = ToolRegistry()
        self.trigger = FailureCuriosityTrigger()
        self.generator = SimulatedCodeGenerator()
        self.evolution = evolution_layer or UC307CognitiveEvolutionLayer()
        self.attempts: List[CuriosityAttempt] = []
        self._seed_basic_tools()

    def _seed_basic_tools(self) -> None:
        basic = [
            Tool(
                name="sumar",
                signature="def sumar(a: float, b: float) -> float:",
                code="def sumar(a: float, b: float) -> float:\n    return a + b\n",
                description="Suma dos números.",
            ),
            Tool(
                name="multiplicar",
                signature="def multiplicar(a: float, b: float) -> float:",
                code="def multiplicar(a: float, b: float) -> float:\n    return a * b\n",
                description="Multiplica dos números.",
            ),
        ]
        for t in basic:
            self.registry.register(t)

    def attempt_problem(
        self,
        problem: str,
        expected_answer: Any,
        max_new_skills: int = 1,
    ) -> CuriosityAttempt:
        """Intenta resolver un problema; si falla, genera una nueva habilidad."""
        attempt = CuriosityAttempt(
            problem=problem,
            initial_tools=self.registry.list_tools(),
            uncertainty_before=self._estimate_uncertainty(problem),
        )
        attempt.trace.append(f"Herramientas iniciales: {attempt.initial_tools}")

        # Intento inicial con herramientas existentes (simulado)
        solved = self._try_solve_with_existing_tools(problem, expected_answer)
        if solved:
            attempt.outcome = SkillOutcome.SOLVED
            attempt.final_answer = expected_answer
            attempt.uncertainty_after = 0.1
            attempt.trace.append("Resuelto con herramientas existentes.")
            self.attempts.append(attempt)
            return attempt

        attempt.trace.append("Fallo inicial. Disparando curiosidad...")

        # Curiosidad: generar nueva herramienta
        for _ in range(max_new_skills):
            hypothesis = self.trigger.hypothesize(problem, self.registry.list_tools())
            code = self.generator.generate(hypothesis)
            new_tool = Tool(
                name=hypothesis["name"],
                signature=hypothesis["signature"],
                code=code,
                description=hypothesis["description"],
                parent_skill=attempt.attempt_id,
            )
            self.registry.register(new_tool)
            attempt.generated_skill = new_tool
            attempt.trace.append(f"Nueva herramienta generada: {new_tool.name}")

            # Reintento con la nueva herramienta
            solved = self._try_solve_with_new_tool(problem, expected_answer, new_tool)
            if solved:
                new_tool.success_count += 1
                attempt.outcome = SkillOutcome.SOLVED
                attempt.final_answer = expected_answer
                attempt.uncertainty_after = 0.1
                attempt.trace.append(f"Problema resuelto tras adquirir {new_tool.name}.")
                break
            else:
                attempt.trace.append(f"La nueva herramienta {new_tool.name} no resolvió el problema.")

        if attempt.outcome != SkillOutcome.SOLVED:
            attempt.outcome = SkillOutcome.FAILED
            attempt.uncertainty_after = attempt.uncertainty_before

        # Evaluar el intento con la capa de plasticidad
        obs = ExecutionObservation(
            agent_id="curiosity_agent",
            task_id=attempt.attempt_id,
            success=attempt.outcome == SkillOutcome.SOLVED,
            reward=1.0 if attempt.outcome == SkillOutcome.SOLVED else -0.5,
            confidence=1.0 - attempt.uncertainty_after,
            coherence=0.7 if attempt.generated_skill else 0.4,
            tool_calls=len(self.registry.list_tools()),
            context={"problem": problem, "new_skill": attempt.generated_skill.name if attempt.generated_skill else None},
        )
        self.evolution.evaluate_execution(obs)
        self.attempts.append(attempt)
        return attempt

    def _estimate_uncertainty(self, problem: str) -> float:
        # Heurística: problemas más largos = mayor incertidumbre inicial
        return min(1.0, 0.3 + len(problem) / 200.0)

    def _try_solve_with_existing_tools(self, problem: str, expected: Any) -> bool:
        # Simulación: solo resuelve problemas que mencionen suma/multiplicación explícitamente
        p = problem.lower()
        if ("suma" in p or "total" in p) and isinstance(expected, (int, float)):
            return True
        if ("producto" in p or "multiplica" in p) and isinstance(expected, (int, float)):
            return True
        return False

    def _try_solve_with_new_tool(self, problem: str, expected: Any, tool: Tool) -> bool:
        # Verifica si la firma suena adecuada para el problema (simulado)
        p = problem.lower()
        if tool.name == "consultar_precio" and ("precio" in p or "costo" in p):
            return True
        if tool.name == "analizar_sentimiento" and ("sentimiento" in p or "sentiment" in p):
            return True
        if tool.name == "detectar_tendencia" and ("tendencia" in p or "trend" in p):
            return True
        if tool.name == "evaluar_riesgo" and ("riesgo" in p or "risk" in p):
            return True
        return False

    def metatool_learn_new_skill(self, problem: str, expected_answer: Any) -> Dict[str, Any]:
        """Metaherramienta pública: 'aprender nueva habilidad'."""
        attempt = self.attempt_problem(problem, expected_answer)
        return attempt.to_dict()

    def summary(self) -> Dict[str, Any]:
        solved = sum(1 for a in self.attempts if a.outcome == SkillOutcome.SOLVED)
        total = len(self.attempts)
        return {
            "total_attempts": total,
            "solved": solved,
            "skills_acquired": [t.to_dict() for t in self.registry.tools.values() if t.parent_skill],
            "success_rate": solved / total if total else 0.0,
        }
