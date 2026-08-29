"""ReflexionLoop — Orquestador del ciclo de autorreflexión para UC-275.

Implementa el ciclo completo de 6 fases:
1. ACTUAR — ejecuta acción con parámetros (opcionalmente ajustados por memoria).
2. OBSERVAR — recopila resultado y métricas.
3. EVALUAR — compara resultado vs expectativas (MetricEvaluator).
4. REFLEXIONAR — identifica causa raíz (SelfCritic).
5. REFINAR — propone y aplica mejoras (SelfRefiner).
6. FINALIZAR — commit on-chain (hash SHA-256 del episodio).

Convergencia: el ciclo se detiene cuando score >= threshold o max_iterations alcanzado.

Inspirado en:
- Reflexion (Shinn et al., NeurIPS 2023): aprendizaje por refuerzo verbal.
- Self-Refine (Madaan et al., 2023): generate → feedback → refine.
- Agents_Reflection_Rewoo_ReAct (sanikacentric): bucle Generate → Reflect → Revise → Accept.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from config import AppConfig, get_config
from critic import SelfCritic
from evaluator import MetricEvaluator
from memory import ReflectionMemory
from models import (
    ActionTrace,
    OutcomeObservation,
    ReflectionEpisode,
    ReflectionOutcome,
    RefinementProposal,
    SelfEvaluation,
)
from refiner import SelfRefiner


class ReflexionLoop:
    """
    Orquesta el ciclo completo de autorreflexión.
    Soporta ejecución síncrona para integración con Flask y testing.
    """

    def __init__(self, agent_id: str,
                 evaluator: MetricEvaluator,
                 critic: SelfCritic,
                 refiner: SelfRefiner,
                 memory: ReflectionMemory,
                 max_iterations: int = 3,
                 convergence_threshold: float = 0.8) -> None:
        self.agent_id = agent_id
        self.evaluator = evaluator
        self.critic = critic
        self.refiner = refiner
        self.memory = memory
        self.max_iterations = max_iterations
        self.convergence_threshold = convergence_threshold

    def execute_with_reflection(
        self,
        action_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
        observe_fn: Callable[[ActionTrace, Dict[str, Any]], OutcomeObservation],
        action_params: Dict[str, Any],
        expected_outcome: Dict[str, float],
        context: Optional[Dict[str, Any]] = None,
    ) -> ReflectionEpisode:
        """
        Ejecuta acción con ciclo de autorreflexión completo (síncrono).

        Args:
            action_fn: función que ejecuta la acción → resultado dict.
            observe_fn: función que observa el resultado → OutcomeObservation.
            action_params: parámetros de la acción.
            expected_outcome: resultado esperado (métricas target).
            context: contexto adicional.
        """
        start_time = time.time()
        context = context or {}
        current_params = dict(action_params)
        action_type = current_params.get("type", current_params.get("_action_type", "unknown"))
        current_params["_action_type"] = action_type

        # PASO 1: Consulta memoria para lecciones previas
        similar = self.memory.recall_similar(ActionTrace(
            agent_id=self.agent_id,
            action_type=action_type,
            action_params=current_params,
        ))
        if similar:
            current_params = self._apply_lessons(current_params, similar)

        # PASO 2: Ejecuta acción
        trace = ActionTrace(
            agent_id=self.agent_id,
            action_type=action_type,
            action_params=current_params,
            context_snapshot=context,
        )
        result = action_fn(current_params)

        # PASO 3: Observa resultado
        observation = observe_fn(trace, result)

        # PASO 4: Evalúa
        evaluation = self.evaluator.evaluate(
            actual=observation.metrics,
            expected=expected_outcome,
        )
        evaluation = evaluation.model_copy(update={"trace_id": trace.trace_id})

        # Estado del episodio
        root_cause = None
        all_refinements: List[RefinementProposal] = []
        iteration = 0

        # PASO 5: Ciclo de refinamiento
        while evaluation.needs_reflection and iteration < self.max_iterations:
            iteration += 1

            root_cause = self.critic.analyze(evaluation, observation, context)
            proposals = self.refiner.propose_refinements(
                evaluation, root_cause, current_params, self.memory
            )

            if not proposals:
                break

            best = proposals[0]
            all_refinements.append(best)
            current_params = self._apply_proposal(current_params, best)

            trace = ActionTrace(
                agent_id=self.agent_id,
                action_type=action_type,
                action_params=current_params,
                context_snapshot=context,
            )
            result = action_fn(current_params)
            observation = observe_fn(trace, result)

            evaluation = self.evaluator.evaluate(
                actual=observation.metrics,
                expected=expected_outcome,
            )
            evaluation = evaluation.model_copy(update={"trace_id": trace.trace_id})

            if evaluation.score >= self.convergence_threshold:
                break

        # PASO 6: Finaliza episodio
        duration = time.time() - start_time
        episode = ReflectionEpisode(
            agent_id=self.agent_id,
            trace_id=trace.trace_id,
            action=trace,
            observation=observation,
            evaluation=evaluation,
            root_cause=root_cause,
            refinements=all_refinements,
            iterations=iteration,
            final_outcome=evaluation.outcome,
            final_score=evaluation.score,
            duration_seconds=round(duration, 4),
        )
        episode = episode.model_copy(update={"reflection_hash": episode.compute_hash()})

        # Almacena en memoria
        self.memory.store(episode)
        return episode

    def _apply_lessons(self, params: Dict[str, Any],
                       similar: List[ReflectionEpisode]) -> Dict[str, Any]:
        """Aplica lecciones de episodios similares exitosos."""
        for ep in similar:
            if ep.final_outcome in (ReflectionOutcome.EXCELLENT, ReflectionOutcome.GOOD):
                for ref in ep.refinements:
                    if ref.net_benefit > 0.2:
                        for k, v in ref.proposed_changes.items():
                            if k in params and isinstance(v, (int, float)):
                                params[k] = v
        return params

    @staticmethod
    def _apply_proposal(params: Dict[str, Any],
                        proposal: RefinementProposal) -> Dict[str, Any]:
        """Aplica propuesta de refinamiento a los parámetros."""
        updated = dict(params)
        for k, v in proposal.proposed_changes.items():
            updated[k] = v
        return updated


class SelfReflectiveAgent:
    """
    Agente autorreflexivo completo — patrón Self-Refine + Reflexion.
    Genera → Critica → Refina → Acepta.

    Criterios ponderados: correctness, completeness, clarity, efficiency.
    """

    def __init__(self,
                 agent_id: str = "agent_default",
                 criteria: Optional[Dict[str, float]] = None,
                 threshold: float = 0.80,
                 max_iterations: int = 3,
                 generate_fn: Optional[Callable[[str], str]] = None,
                 critique_fn: Optional[Callable[[str, str], Dict[str, Dict]]] = None) -> None:
        self.agent_id = agent_id
        self.criteria = criteria or {
            "correctness": 0.40,
            "completeness": 0.25,
            "clarity": 0.20,
            "efficiency": 0.15,
        }
        self.threshold = threshold
        self.max_iterations = max_iterations
        self._generate_fn = generate_fn or self._default_generate
        self._critique_fn = critique_fn or self._default_critique
        self.evaluator = MetricEvaluator(self.criteria)
        self.memory = ReflectionMemory()
        self.history: List[Dict[str, Any]] = []

    def run(self, task: str) -> Dict[str, Any]:
        """Ejecuta ciclo de autorreflexión Self-Refine sobre una tarea."""
        output = self._generate_fn(task)
        history = []

        for i in range(1, self.max_iterations + 1):
            critique = self._critique_fn(task, output)
            criteria_scores = {k: float(v.get("score", 0.5)) for k, v in critique.items()}
            evaluation = self.evaluator.evaluate_text_output(criteria_scores)

            failed = {
                k: v.get("feedback", "")
                for k, v in critique.items()
                if v.get("status") == "FAIL"
            }
            history.append({
                "iteration": i,
                "score": evaluation.score,
                "outcome": evaluation.outcome.value,
                "failed_criteria": list(failed.keys()),
                "critique": critique,
            })

            if evaluation.score >= self.threshold:
                result = {
                    "output": output,
                    "score": round(evaluation.score, 4),
                    "iterations": i,
                    "accepted": True,
                    "outcome": evaluation.outcome.value,
                    "history": history,
                }
                self.history.append(result)
                return result

            # Refina solo criterios fallidos
            output = self._refine(task, output, failed)

        # Máx iteraciones: entrega mejor versión
        result = {
            "output": output,
            "score": round(history[-1]["score"], 4) if history else 0.0,
            "iterations": self.max_iterations,
            "accepted": False,
            "outcome": history[-1]["outcome"] if history else "unknown",
            "history": history,
        }
        self.history.append(result)
        return result

    def _refine(self, task: str, output: str, failed: Dict[str, str]) -> str:
        """Refina output usando feedback de criterios fallidos."""
        feedback = "; ".join(f"{k}: {v}" for k, v in failed.items())
        return self._generate_fn(
            f"Mejora la siguiente salida atendiendo estas críticas: {feedback}\n"
            f"Tarea original: {task}\nSalida anterior: {output}"
        )

    @staticmethod
    def _default_generate(prompt: str) -> str:
        return f"[Generated output for: {prompt[:80]}...]"

    @staticmethod
    def _default_critique(task: str, output: str) -> Dict[str, Dict]:
        """Crítica simulada (para demo sin LLM real)."""
        import hashlib
        seed = int(hashlib.md5((task + output).encode()).hexdigest()[:8], 16)
        base = 0.6 + (seed % 30) / 100.0
        return {
            "correctness": {"status": "PASS" if base > 0.65 else "FAIL",
                           "score": min(1.0, base + 0.15), "feedback": "Evaluación de corrección"},
            "completeness": {"status": "FAIL" if base < 0.7 else "PASS",
                            "score": min(1.0, base + 0.05), "feedback": "Falta cubrir caso borde"},
            "clarity": {"status": "PASS", "score": min(1.0, base + 0.1), "feedback": "Claro"},
            "efficiency": {"status": "PASS", "score": min(1.0, base + 0.08), "feedback": "Aceptable"},
        }
