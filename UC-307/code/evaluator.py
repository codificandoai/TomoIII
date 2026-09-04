"""Motor de evaluación de tres niveles para agentes autónomos (UC-307).

Integra:
  - Nivel 1: tasa de éxito de la tarea.
  - Nivel 2: puntuación de calidad (LLM Juez real o simulado).
  - Nivel 3: métricas de eficiencia (tokens, herramientas, latencia).

Con esos tres niveles calcula un fitness combinado y delega en
`DecisionEngine` la recomendación del orquestador central.
"""
from __future__ import annotations

import random
import time
from typing import Optional

from config import THRESHOLDS
from decision_engine import DecisionEngine
from llm_judge import LLMJudge
from metrics import METRICS
from models import AgentDNA, AgentEvaluation, DecisionAction, EfficiencyMetrics, EvaluationInput


class AgentPerformanceEvaluator:
    """Evalúa un agente y recomienda su destino dentro de la población."""

    def __init__(
        self,
        thresholds=THRESHOLDS,
        llm_judge: Optional[LLMJudge] = None,
        decision_engine: Optional[DecisionEngine] = None,
        metrics_registry=METRICS,
    ):
        self.cfg = thresholds
        self.judge = llm_judge or LLMJudge()
        self.engine = decision_engine or DecisionEngine(thresholds)
        self.metrics = metrics_registry

    def normalize_quality(self, quality_score: float, scale: float = 5.0) -> float:
        """Convierte calidad a escala 0..1 usando la escala indicada."""
        scale = max(0.1, scale)
        return min(1.0, max(0.0, quality_score / scale))

    def compute_efficiency_score(self, efficiency: EfficiencyMetrics) -> float:
        """Puntuación 0..1 de eficiencia a partir de tokens, llamadas y latencia."""
        token_ratio = min(1.0, efficiency.tokens_used / max(1, self.cfg.max_tokens))
        tool_ratio = min(1.0, efficiency.tool_calls / max(1, self.cfg.max_tool_calls))
        latency_ratio = min(1.0, efficiency.latency_seconds / max(0.1, self.cfg.max_latency_seconds))

        # Cada métrica penaliza linealmente hasta el límite
        token_penalty = 1.0 - token_ratio
        tool_penalty = 1.0 - tool_ratio
        latency_penalty = 1.0 - latency_ratio

        score = (token_penalty + tool_penalty + latency_penalty) / 3.0
        return max(0.0, min(1.0, score))

    def compute_fitness(
        self,
        success_rate: float,
        normalized_quality: float,
        efficiency_score: float,
    ) -> float:
        """Fitness combinado ponderado por los pesos configurables."""
        weights = self.cfg.weights
        fitness = (
            weights["success_rate"] * success_rate
            + weights["quality"] * normalized_quality
            + weights["efficiency"] * efficiency_score
        )
        return max(0.0, min(1.0, fitness))

    def evaluate(
        self,
        input_data: EvaluationInput,
        population_size: Optional[int] = None,
    ) -> AgentEvaluation:
        """Ejecuta el análisis completo de performance y registra métricas."""

        # Nivel 2: si hay descripción y resultado, el LLM Juez puede validar
        quality_score = input_data.quality_score
        if input_data.task_description and input_data.result_text and input_data.quality_score <= 1.0:
            # Solo recalculamos si la calidad parece no venir de una escala 1..5 ya evaluada
            judged_quality = self.judge.evaluate(
                input_data.task_description,
                input_data.result_text,
                expected_outcome=input_data.task_description,
            )
            quality_score = judged_quality

        normalized_quality = self.normalize_quality(quality_score, scale=input_data.quality_scale)
        efficiency_score = self.compute_efficiency_score(input_data.efficiency)
        fitness = self.compute_fitness(
            input_data.task_success_rate,
            normalized_quality,
            efficiency_score,
        )

        verdict, actions, reasoning = self.engine.decide(
            success_rate=input_data.task_success_rate,
            normalized_quality=normalized_quality,
            efficiency_score=efficiency_score,
            fitness=fitness,
            dna=input_data.dna,
            mate_dna=input_data.mate_dna,
            population_size=population_size,
        )

        status = "success" if input_data.task_success_rate >= self.cfg.success_low else "failure"
        self.metrics.record_evaluation(
            status=status,
            quality=quality_score,
            fitness=fitness,
            decision=verdict.value,
            tokens=input_data.efficiency.tokens_used,
            tool_calls=input_data.efficiency.tool_calls,
            latency=input_data.efficiency.latency_seconds,
        )

        return AgentEvaluation(
            agent_id=input_data.agent_id,
            task_success_rate=input_data.task_success_rate,
            quality_score=quality_score,
            normalized_quality=normalized_quality,
            efficiency=input_data.efficiency,
            efficiency_score=efficiency_score,
            fitness=fitness,
            verdict=verdict,
            actions=actions,
            reasoning=reasoning,
        )

    # ------------------------------------------------------------------
    # Simulador de ejecución de tarea (compatible con el demo original)
    # ------------------------------------------------------------------
    def simulate_task(
        self,
        description: str,
        task_type: str = "unknown",
        subjective: bool = False,
        expected_outcome: str = "",
    ) -> dict:
        """Simula la ejecución de un agente autónomo y la evalúa con el juez."""
        time.sleep(random.uniform(0.05, 0.15))  # simulación breve
        success = random.random() > 0.2
        result_text = (
            "El análisis de precios indica una elasticidad de -1.5, recomendando subir el precio un 5%."
            if success
            else "Error: Timeout conectando con la base de datos de competencia."
        )

        quality = 5.0
        if subjective and success:
            quality = self.judge.evaluate(description, result_text, expected_outcome)
        elif not success:
            quality = 1.0

        return {
            "success": success,
            "result_text": result_text,
            "quality_score": quality,
            "tokens_used": random.randint(500, 3000),
            "tool_calls": random.randint(1, 6),
            "latency_seconds": round(random.uniform(0.1, 1.2), 2),
            "task_type": task_type,
        }

    def evaluate_task(self, task: dict) -> AgentEvaluation:
        """Envuelve `simulate_task` en una evaluación completa."""
        sim = self.simulate_task(
            description=task.get("description", "tarea"),
            task_type=task.get("type", "unknown"),
            subjective=task.get("subjective", False),
            expected_outcome=task.get("expected", ""),
        )
        success_rate = 1.0 if sim["success"] else 0.0
        return self.evaluate(
            EvaluationInput(
                agent_id=task.get("agent_id", f"sim_{random.randint(1000, 9999)}"),
                task_success_rate=success_rate,
                quality_score=sim["quality_score"],
                efficiency=EfficiencyMetrics(
                    tokens_used=sim["tokens_used"],
                    tool_calls=sim["tool_calls"],
                    latency_seconds=sim["latency_seconds"],
                ),
                task_description=task.get("description"),
                result_text=sim["result_text"],
            )
        )
