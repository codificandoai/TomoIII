"""RecursivePrompter — Orquestador principal del ciclo recursivo para UC-276.

Implementa el ciclo completo de recursive prompting:
1. GENERATE — produce versión inicial del output.
2. EVALUATE — evalúa calidad contra criterios.
3. DECIDE — si cumple target, COMMIT; si no, continuar.
4. REFINE — selecciona estrategia y genera versión mejorada.
5. VERIFY — verifica que no haya degradación (rollback si degrada).
6. LEARN — registra versión y actualiza historial.
7. REPEAT — hasta convergencia, estancamiento o max_iterations.

Cada versión V_n es INPUT de V_{n+1} — propiedad recursiva fundamental.

Inspirado en:
- Gödel Agent (Arvid-pku): auto-referencia con propose → verify → apply.
- recursive-agents (hankbesser): three-phase iterative refinement.
- recursive-improve (kayba-ai): improve → run → evaluate → keep/revert.
- rsi-loop (clawinfra): Observe → Analyze → Fix → Verify.
- self_improving_coding_agent (MaximeRobeyns): evaluate → improve → re-evaluate.
"""
from __future__ import annotations

import hashlib
import json
import time
from collections import deque
from typing import Any, Callable, Dict, List, Optional

from config import get_config
from models import (
    QualityCriteria,
    QualityReport,
    RecursiveSession,
    RecursiveVersion,
    RefinementStrategy,
    SessionStatus,
)
from quality import QualityEvaluator
from refiner import Refiner
from stagnation import StagnationDetector


class RecursivePrompter:
    """
    Orquestador principal del recursive prompting.
    Ejecuta el ciclo: generar → evaluar → refinar → repetir.
    """

    def __init__(self, agent_id: str,
                 criteria: List[QualityCriteria],
                 max_iterations: int = 5,
                 target_score: float = 0.85,
                 min_acceptable_score: float = 0.60,
                 evaluator: Optional[QualityEvaluator] = None,
                 refiner: Optional[Refiner] = None,
                 stagnation_detector: Optional[StagnationDetector] = None) -> None:
        self.agent_id = agent_id
        self.criteria = criteria
        self.max_iterations = max_iterations
        self.target_score = target_score
        self.min_acceptable = min_acceptable_score
        self.evaluator = evaluator or QualityEvaluator(criteria)
        self.refiner = refiner or Refiner()
        self.stagnation_detector = stagnation_detector or StagnationDetector.from_config()
        self.sessions: deque = deque(maxlen=200)

    def run(self, input_data: str,
            task_description: str,
            context: Optional[Dict[str, Any]] = None,
            initial_version: Optional[str] = None,
            generate_fn: Optional[Callable[[str, Dict], str]] = None) -> RecursiveSession:
        """
        Ejecuta ciclo recursivo completo (síncrono).

        Args:
            input_data: input original a procesar.
            task_description: descripción de lo que se debe producir.
            context: contexto adicional (audiencia, objetivo, etc.).
            initial_version: borrador inicial (si existe).
            generate_fn: función de generación custom (opcional).
        """
        start_time = time.time()
        context = context or {}

        session = RecursiveSession(
            agent_id=self.agent_id,
            task_description=task_description,
            initial_input=input_data,
        )

        trajectory: List[float] = []

        # ── ITERACIÓN 0: Generar versión inicial ──
        if initial_version:
            content = initial_version
        elif generate_fn:
            content = generate_fn(input_data, context)
        else:
            content = self._default_generate(input_data, task_description, context)

        current_version = RecursiveVersion.create(
            iteration=0,
            content=content,
            strategy=None,
            prompt="initial_generation",
            metadata={"context_keys": list(context.keys())},
        )

        # Evalúa versión inicial
        quality_report = self.evaluator.evaluate(current_version, input_data, task_description)
        current_version = current_version.model_copy(update={"quality_report": quality_report})
        session.versions.append(current_version)
        trajectory.append(quality_report.overall_score)

        # ── CICLO RECURSIVO ──
        iteration = 0
        status = SessionStatus.RUNNING
        convergence_reason = None

        while iteration < self.max_iterations:
            iteration += 1

            # ¿Ya cumple target?
            if quality_report.overall_score >= self.target_score:
                status = SessionStatus.CONVERGED
                convergence_reason = (
                    f"Target reached: {quality_report.overall_score:.3f} >= {self.target_score}"
                )
                break

            # ¿Está estancado?
            is_stagnated, stagnation_reason = self.stagnation_detector.is_stagnated(trajectory)
            if is_stagnated:
                status = SessionStatus.STAGNATED
                convergence_reason = f"Stopped: {stagnation_reason}"
                break

            # Selecciona estrategia de refinamiento
            strategy = self.refiner.select_strategy(quality_report, self.criteria, iteration)

            # Genera versión refinada
            new_content = self.refiner.refine(
                current_version=current_version,
                quality_report=quality_report,
                task_description=task_description,
                strategy=strategy,
                extra_context=context,
            )

            # Crea nueva versión
            new_version = RecursiveVersion.create(
                iteration=iteration,
                content=new_content,
                parent_version=current_version.version_id,
                strategy=strategy,
                prompt=self.refiner.get_prompt_for_strategy(strategy, quality_report, context),
                metadata={"context_keys": list(context.keys())},
            )

            # Evalúa nueva versión
            new_quality = self.evaluator.evaluate(new_version, input_data, task_description)
            delta = new_quality.overall_score - quality_report.overall_score

            # ¿Degradación? → Rollback
            if self.stagnation_detector.should_rollback(new_quality.overall_score,
                                                        quality_report.overall_score):
                new_version = new_version.model_copy(update={
                    "quality_report": new_quality,
                    "delta_from_parent": delta,
                    "metadata": {**new_version.metadata, "discarded": True, "reason": "degradation"},
                })
                session.versions.append(new_version)
                continue

            # Acepta versión mejorada
            new_version = new_version.model_copy(update={
                "quality_report": new_quality,
                "delta_from_parent": delta,
            })

            session.versions.append(new_version)
            trajectory.append(new_quality.overall_score)
            current_version = new_version
            quality_report = new_quality

            # ¿Aceptable con rendimientos decrecientes?
            if quality_report.overall_score >= self.min_acceptable and delta < 0.02:
                status = SessionStatus.CONVERGED
                convergence_reason = (
                    f"Acceptable with diminishing returns: {quality_report.overall_score:.3f}"
                )
                break

        # Finaliza sesión
        if status == SessionStatus.RUNNING:
            if quality_report.overall_score >= self.min_acceptable:
                status = SessionStatus.MAX_ITERATIONS
                convergence_reason = (
                    f"Max iterations with acceptable quality: {quality_report.overall_score:.3f}"
                )
            else:
                status = SessionStatus.FAILED
                convergence_reason = (
                    f"Failed to reach acceptable quality: {quality_report.overall_score:.3f}"
                )

        duration = time.time() - start_time
        session = session.model_copy(update={
            "final_version_id": current_version.version_id,
            "total_iterations": len([v for v in session.versions if not v.metadata.get("discarded")]) - 1,
            "status": status,
            "convergence_reason": convergence_reason,
            "total_duration_seconds": round(duration, 4),
            "session_hash": session.compute_hash(),
        })

        self.sessions.append(session)
        return session

    def get_stats(self) -> Dict[str, Any]:
        """Estadísticas del prompter."""
        if not self.sessions:
            return {
                "total_sessions": 0,
                "avg_score": 0.0,
                "avg_iterations": 0.0,
                "convergence_rate": 0.0,
                "strategies_used": {},
            }

        scores = [s.final_score for s in self.sessions]
        iterations = [s.total_iterations for s in self.sessions]
        converged = sum(1 for s in self.sessions if s.status == SessionStatus.CONVERGED)

        strategy_counts: Dict[str, int] = {}
        for s in self.sessions:
            for v in s.versions:
                if v.refinement_strategy:
                    key = v.refinement_strategy.value
                    strategy_counts[key] = strategy_counts.get(key, 0) + 1

        return {
            "total_sessions": len(self.sessions),
            "avg_score": round(sum(scores) / len(scores), 4) if scores else 0.0,
            "avg_iterations": round(sum(iterations) / len(iterations), 2) if iterations else 0.0,
            "convergence_rate": round(converged / len(self.sessions), 4),
            "strategies_used": strategy_counts,
        }

    @staticmethod
    def _default_generate(input_data: str, task: str, context: Dict) -> str:
        """Generación por defecto (simulada, sin LLM real)."""
        # Simula resumen/procesamiento del input
        words = input_data.split()
        if len(words) > 30:
            summary = " ".join(words[:15]) + " ... " + " ".join(words[-10:])
        else:
            summary = input_data
        return f"Resumen de '{task[:50]}': {summary}"


class RSILoop:
    """
    Recursive Self-Improvement Loop — patrón RSI avanzado.
    Implementa el ciclo de auto-mejora recursiva estilo Gödel Agent:
    Propose → Verify → Apply → Benchmark → Evaluate → Learn.

    Cada iteración el agente puede proponer mejoras a su propia lógica.
    """

    def __init__(self, agent_id: str = "rsi_agent",
                 max_cycles: int = 5,
                 improvement_threshold: float = 0.05) -> None:
        self.agent_id = agent_id
        self.max_cycles = max_cycles
        self.improvement_threshold = improvement_threshold
        self.history: List[Dict[str, Any]] = []
        self._current_logic_version = 0

    def run_cycle(self, task: str, current_output: str,
                  evaluate_fn: Optional[Callable[[str], float]] = None) -> Dict[str, Any]:
        """
        Ejecuta un ciclo RSI completo.
        
        Args:
            task: tarea a realizar.
            current_output: output actual a mejorar.
            evaluate_fn: función de evaluación externa.
        """
        evaluate_fn = evaluate_fn or self._default_evaluate

        baseline_score = evaluate_fn(current_output)
        best_output = current_output
        best_score = baseline_score
        cycle_history = []

        for cycle in range(self.max_cycles):
            # 1. PROPOSE: genera versión mejorada
            proposed = self._propose_improvement(best_output, task, cycle)

            # 2. VERIFY: verifica que no rompe
            is_valid, reason = self._verify(proposed)
            if not is_valid:
                cycle_history.append({
                    "cycle": cycle + 1,
                    "action": "rejected",
                    "reason": reason,
                    "score": best_score,
                })
                continue

            # 3. BENCHMARK: evalúa nueva versión
            new_score = evaluate_fn(proposed)

            # 4. EVALUATE: compara con versión anterior
            improvement = new_score - best_score

            if improvement >= self.improvement_threshold:
                # 5. APPLY: acepta mejora
                best_output = proposed
                best_score = new_score
                self._current_logic_version += 1
                cycle_history.append({
                    "cycle": cycle + 1,
                    "action": "accepted",
                    "improvement": round(improvement, 4),
                    "score": round(new_score, 4),
                    "logic_version": self._current_logic_version,
                })
            else:
                # REVERT: descarta
                cycle_history.append({
                    "cycle": cycle + 1,
                    "action": "reverted",
                    "improvement": round(improvement, 4),
                    "score": round(best_score, 4),
                    "reason": f"Improvement {improvement:.3f} < threshold {self.improvement_threshold}",
                })

            # ¿Convergió?
            if best_score >= 0.95:
                break

        # 6. LEARN: registra resultado
        result = {
            "agent_id": self.agent_id,
            "task": task[:100],
            "baseline_score": round(baseline_score, 4),
            "final_score": round(best_score, 4),
            "total_improvement": round(best_score - baseline_score, 4),
            "cycles_run": len(cycle_history),
            "accepted_changes": sum(1 for c in cycle_history if c["action"] == "accepted"),
            "logic_version": self._current_logic_version,
            "final_output": best_output,
            "history": cycle_history,
        }
        self.history.append(result)
        return result

    def _propose_improvement(self, current: str, task: str, cycle: int) -> str:
        """Propone mejora al output actual (simula auto-mejora)."""
        # Simula refinamiento progresivo
        improvements = [
            lambda c: c + " Además, se consideran factores adicionales.",
            lambda c: "En resumen: " + c.split(".")[0] + ". " + ". ".join(c.split(".")[1:]),
            lambda c: c.replace("  ", " ").strip() + " Conclusión integrada.",
            lambda c: f"[Optimizado v{cycle + 1}] " + c[:int(len(c) * 0.85)],
            lambda c: c + " Finalmente, esto asegura la calidad del resultado.",
        ]
        fn = improvements[cycle % len(improvements)]
        return fn(current)

    @staticmethod
    def _verify(proposed: str) -> tuple:
        """Verifica que la propuesta es válida."""
        if not proposed or len(proposed) < 10:
            return False, "Output too short"
        if len(proposed) > 50000:
            return False, "Output too long"
        return True, ""

    @staticmethod
    def _default_evaluate(output: str) -> float:
        """Evaluación por defecto basada en heurísticas."""
        score = 0.5
        if len(output) > 50:
            score += 0.1
        if len(output) > 200:
            score += 0.1
        sentences = [s for s in output.split(".") if s.strip()]
        if len(sentences) >= 3:
            score += 0.1
        connectors = ["además", "por lo tanto", "finalmente", "en resumen",
                      "moreover", "therefore", "finally", "in summary"]
        if any(c in output.lower() for c in connectors):
            score += 0.1
        return min(1.0, score)
