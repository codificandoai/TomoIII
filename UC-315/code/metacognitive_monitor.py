"""UC-313 — Monitor Metacognitivo.

Implementa la Red de Nivel 1 del diagrama brain.png: no ve el mundo exterior, sino
que observa la actividad interna de la Red Ejecutora (workspace SAM, señales,
hipótesis, estados BDI/Juice, predicciones ToT, resultados de ejecución) y emite
un veredicto ejecutivo que alimenta la plasticidad y el bucle de autoconciencia.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from cognitive_evolution_layer import (
    ExecutionObservation,
    PlasticityDecision,
    UC307CognitiveEvolutionLayer,
)
from sam import MetacognitionModule


class MetacognitiveMonitor:
    """Observa estados internos del sistema y emite diagnóstico metacognitivo."""

    def __init__(
        self,
        evolution_layer: Optional[UC307CognitiveEvolutionLayer] = None,
    ) -> None:
        self.sam_meta = MetacognitionModule()
        self.evolution = evolution_layer or UC307CognitiveEvolutionLayer()

    def evaluate_workspace(
        self,
        workspace: Any,
        selected_strategy: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Evalúa el workspace global con el monitor metacognitivo."""
        return self.sam_meta.evaluate(workspace, selected_strategy=selected_strategy)

    def observe_internal_state(
        self,
        workspace: Any,
        trading_output: Dict[str, Any],
        tot_prediction: Optional[Dict[str, Any]] = None,
        execution_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Meta-red: único input es la actividad interna de la red ejecutora.
        Devuelve un veredicto y una observación de ejecución lista para UC-307.
        """
        meta = self.sam_meta.evaluate(workspace)
        confidence = workspace.self_model.get("confidence_level", 1.0)
        coherence = self._compute_internal_coherence(
            workspace, trading_output, tot_prediction, execution_result
        )

        # Contar anomalías internas
        anomalies: List[str] = []
        if meta.get("abort"):
            anomalies.append("sam_abort")
        if meta.get("need_review"):
            anomalies.append("sam_review")
        if workspace.broadcast.get("flags"):
            anomalies.extend([f"broadcast_flag:{f}" for f in workspace.broadcast["flags"]])

        status = trading_output.get("status", "unknown")
        errors = 1 if status in ("failed", "aborted_by_sam", "blocked") else 0

        obs = ExecutionObservation(
            agent_id=trading_output.get("selected_strategy") or "global_workspace",
            success=errors == 0,
            reward=1.0 if errors == 0 else -1.0,
            confidence=confidence,
            coherence=coherence,
            errors=errors,
            tool_calls=len(workspace.perception.get("signals", [])),
            activations={
                "self_confidence": confidence,
                "internal_coherence": coherence,
                "sam_issues": len(meta.get("issues", [])),
            },
            context={
                "workspace_flags": workspace.broadcast.get("flags", []),
                "status": status,
                "recommendation": meta.get("recommendation"),
            },
        )
        plasticity = self.evolution.evaluate_execution(obs)

        return {
            "sam_meta": meta,
            "plasticity": plasticity.to_dict(),
            "verdict": self._map_verdict(meta, plasticity),
            "coherence": coherence,
            "anomalies": anomalies,
        }

    @staticmethod
    def _compute_internal_coherence(
        workspace: Any,
        trading_output: Dict[str, Any],
        tot_prediction: Optional[Dict[str, Any]],
        execution_result: Optional[Dict[str, Any]],
    ) -> float:
        """Mide coherencia entre señales del workspace, ToT y ejecución."""
        scores = [workspace.self_model.get("confidence_level", 0.5)]
        if tot_prediction and tot_prediction.get("final_prediction"):
            scores.append(tot_prediction["final_prediction"].get("confidence", 0.5))
        exec_success = 1.0 if trading_output.get("status") not in ("failed", "aborted_by_sam") else 0.0
        scores.append(exec_success)
        if execution_result and isinstance(execution_result, dict):
            scores.append(1.0 if execution_result.get("success") else 0.0)
        return float(sum(scores) / len(scores)) if scores else 0.5

    @staticmethod
    def _map_verdict(meta: Dict[str, Any], plasticity: Any) -> str:
        if meta.get("abort") or plasticity.decision == PlasticityDecision.STOP:
            return "STOP"
        if meta.get("need_review") or plasticity.decision == PlasticityDecision.REVIEW:
            return "REVIEW"
        if plasticity.decision in {PlasticityDecision.REVERT, PlasticityDecision.ELIMINATE}:
            return "REVIEW"
        return "PROCEED"
