"""
UC-325 — Monitor de Convergencia para el Motor de Razonamiento Autorreflexivo.

Decide cuándo el bucle de razonamiento debe detenerse basándose en:
1. Convergencia de confianza: la confianza deja de cambiar significativamente.
2. Quality gates: todas las dimensiones superan umbrales mínimos.
3. Stall detection: el razonamiento no progresa (misma info, mismos gaps).
4. Max rounds: límite duro de iteraciones.
5. Hallucination threshold: demasiadas alucinaciones detectadas.

Reemplaza la ausencia de convergencia intra-episodio en self_awareness_loop.py.
"""

from typing import List, Dict, Optional
import math

from reasoning_models import (
    ReasoningState,
    ReasoningVerdict,
    QualityScore,
    HallucinationReport,
    LoopIteration,
)


class ConvergenceMonitor:
    """
    Monitorea la convergencia del bucle de razonamiento y decide
    cuándo detener las iteraciones.
    """

    def __init__(
        self,
        min_convergence_delta: float = 0.02,
        stall_threshold: int = 2,
        hallucination_abort_threshold: float = 0.8,
        min_confidence_for_convergence: float = 0.6,
    ):
        self.min_convergence_delta = min_convergence_delta
        self.stall_threshold = stall_threshold
        self.hallucination_abort_threshold = hallucination_abort_threshold
        self.min_confidence = min_confidence_for_convergence
        self._stall_count: int = 0
        self._prev_chunk_count: int = 0
        self._prev_hypothesis_count: int = 0

    @property
    def stall_count(self) -> int:
        return self._stall_count

    def should_stop(
        self,
        state: ReasoningState,
        quality: Optional[QualityScore] = None,
        hallucination: Optional[HallucinationReport] = None,
    ) -> Dict[str, any]:
        """
        Evalúa si el bucle debe detenerse.

        Retorna:
        - stop: bool
        - verdict: ReasoningVerdict
        - reason: str
        - metrics: dict con métricas de convergencia
        """
        # 1. Max rounds alcanzado
        if state.round_number >= state.max_rounds:
            return {
                "stop": True,
                "verdict": ReasoningVerdict.MAX_ROUNDS,
                "reason": f"Maximum rounds reached ({state.max_rounds})",
                "metrics": self._build_metrics(state, quality),
            }

        # 2. Hallucination abort
        if hallucination and hallucination.severity >= self.hallucination_abort_threshold:
            return {
                "stop": True,
                "verdict": ReasoningVerdict.HALLUCINATION_DETECTED,
                "reason": f"Critical hallucination detected (severity={hallucination.severity:.2f})",
                "metrics": self._build_metrics(state, quality),
            }

        # 3. Quality gates todas pasadas + confianza suficiente
        if quality and quality.passed:
            trajectory = state.confidence_trajectory
            current_confidence = trajectory[-1] if trajectory else 0.0

            if current_confidence >= self.min_confidence:
                return {
                    "stop": True,
                    "verdict": ReasoningVerdict.CONVERGED,
                    "reason": f"All quality gates passed, confidence={current_confidence:.2f}",
                    "metrics": self._build_metrics(state, quality),
                }

        # 4. Convergencia de confianza (delta < threshold)
        if len(state.confidence_trajectory) >= 2:
            delta = abs(
                state.confidence_trajectory[-1] - state.confidence_trajectory[-2]
            )
            current = state.confidence_trajectory[-1]

            if delta < self.min_convergence_delta and current >= self.min_confidence:
                return {
                    "stop": True,
                    "verdict": ReasoningVerdict.CONVERGED,
                    "reason": f"Confidence converged (delta={delta:.4f} < {self.min_convergence_delta})",
                    "metrics": self._build_metrics(state, quality),
                }

        # 5. Stall detection
        current_chunks = len(state.all_chunks)
        current_hypotheses = len(state.active_hypotheses)

        if (
            current_chunks == self._prev_chunk_count
            and current_hypotheses == self._prev_hypothesis_count
        ):
            self._stall_count += 1
        else:
            self._stall_count = 0

        self._prev_chunk_count = current_chunks
        self._prev_hypothesis_count = current_hypotheses

        if self._stall_count >= self.stall_threshold:
            return {
                "stop": True,
                "verdict": ReasoningVerdict.STALLED,
                "reason": f"No progress for {self._stall_count} consecutive rounds",
                "metrics": self._build_metrics(state, quality),
            }

        # 6. Insufficient data: no chunks y ya pasaron rondas
        if state.round_number >= 2 and not state.all_chunks:
            return {
                "stop": True,
                "verdict": ReasoningVerdict.INSUFFICIENT_DATA,
                "reason": "No chunks retrieved after multiple rounds",
                "metrics": self._build_metrics(state, quality),
            }

        # Continuar
        return {
            "stop": False,
            "verdict": None,
            "reason": "Continue reasoning",
            "metrics": self._build_metrics(state, quality),
        }

    def compute_convergence_delta(self, state: ReasoningState) -> float:
        """Calcula el cambio de confianza respecto a la iteración anterior."""
        if len(state.confidence_trajectory) < 2:
            return 1.0  # Primera ronda, máxima variación

        return abs(
            state.confidence_trajectory[-1] - state.confidence_trajectory[-2]
        )

    def compute_progress_score(self, state: ReasoningState) -> float:
        """
        Score 0-1 de progreso del razonamiento.

        Combina: hipótesis activas, gaps llenados, y confianza actual.
        """
        if not state.hypotheses:
            return 0.0

        active_ratio = len(state.active_hypotheses) / max(len(state.hypotheses), 1)
        total_gaps = len(state.gaps)
        filled_ratio = (
            sum(1 for g in state.gaps.values() if g.filled) / total_gaps
            if total_gaps > 0
            else 1.0
        )
        confidence = (
            state.confidence_trajectory[-1]
            if state.confidence_trajectory
            else 0.0
        )

        return (
            0.30 * active_ratio
            + 0.30 * filled_ratio
            + 0.40 * confidence
        )

    def get_trajectory_analysis(
        self,
        trajectory: List[float],
    ) -> Dict[str, any]:
        """
        Analiza la trayectoria de confianza.

        Detecta: mejora, estancamiento, degradación, oscilación.
        """
        if len(trajectory) < 2:
            return {
                "trend": "insufficient_data",
                "avg_delta": 0.0,
                "direction": "unknown",
                "oscillating": False,
            }

        deltas = [
            trajectory[i] - trajectory[i - 1]
            for i in range(1, len(trajectory))
        ]

        avg_delta = sum(deltas) / len(deltas)
        positive_count = sum(1 for d in deltas if d > 0)
        negative_count = sum(1 for d in deltas if d < 0)

        # Detectar oscilación: cambios frecuentes de dirección
        direction_changes = 0
        for i in range(1, len(deltas)):
            if (deltas[i] > 0) != (deltas[i - 1] > 0):
                direction_changes += 1

        oscillating = direction_changes >= len(deltas) * 0.5 if len(deltas) >= 2 else False

        if oscillating:
            trend = "oscillating"
        elif avg_delta > self.min_convergence_delta:
            trend = "improving"
        elif avg_delta < -self.min_convergence_delta:
            trend = "degrading"
        else:
            trend = "converging"

        direction = "up" if avg_delta > 0 else ("down" if avg_delta < 0 else "flat")

        return {
            "trend": trend,
            "avg_delta": round(avg_delta, 4),
            "direction": direction,
            "oscillating": oscillating,
            "positive_rounds": positive_count,
            "negative_rounds": negative_count,
            "total_rounds": len(deltas),
        }

    def _build_metrics(
        self,
        state: ReasoningState,
        quality: Optional[QualityScore],
    ) -> Dict[str, any]:
        """Construye métricas de convergencia."""
        trajectory = state.confidence_trajectory
        return {
            "round": state.round_number,
            "max_rounds": state.max_rounds,
            "chunks": len(state.all_chunks),
            "active_hypotheses": len(state.active_hypotheses),
            "unfilled_gaps": len(state.unfilled_gaps),
            "confidence": round(trajectory[-1], 4) if trajectory else 0.0,
            "convergence_delta": round(self.compute_convergence_delta(state), 4),
            "progress_score": round(self.compute_progress_score(state), 4),
            "stall_count": self._stall_count,
            "quality_overall": round(quality.overall, 4) if quality else None,
            "quality_passed": quality.passed if quality else False,
            "trajectory_analysis": self.get_trajectory_analysis(trajectory),
        }

    def reset(self) -> None:
        """Resetea estado interno."""
        self._stall_count = 0
        self._prev_chunk_count = 0
        self._prev_hypothesis_count = 0
