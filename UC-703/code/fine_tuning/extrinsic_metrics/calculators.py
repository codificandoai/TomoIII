"""Cálculo de métricas extrínsecas de negocio y recuperación contextual."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fine_tuning.extrinsic_metrics.models_em import (
    ApplicationEvent,
    ContextualRecallMetrics,
    ExtrinsicMetrics,
    InferenceEvent,
    UnifiedSession,
)


class ExtrinsicCalculator:
    """
    Calcula métricas de valor de negocio a partir de sesiones unificadas.
    """

    def __init__(self) -> None:
        pass

    def calculate(
        self,
        sessions: List[UnifiedSession],
        window_start: float,
        window_end: float,
        baseline_retention_rate: Optional[float] = None,
    ) -> ExtrinsicMetrics:
        completed = 0
        failed = 0
        abandoned = 0
        total_cost = 0.0
        total_revenue = 0.0
        resolution_times: List[float] = []
        total_tasks = 0

        completed_session_ids = set()
        for session in sessions:
            started = None
            ended = None
            has_completed = False
            for app in session.application_events:
                if app.event_type == "task_completed":
                    completed += 1
                    total_tasks += 1
                    has_completed = True
                elif app.event_type == "task_failed":
                    failed += 1
                    total_tasks += 1
                elif app.event_type == "user_abandoned":
                    abandoned += 1
                    total_tasks += 1
                elif app.event_type == "session_started":
                    started = app.timestamp
                if app.event_type in ("task_completed", "task_failed", "user_abandoned"):
                    ended = app.timestamp
                total_revenue += app.revenue_usd
            if started and ended:
                resolution_times.append(ended - started)
            if has_completed:
                completed_session_ids.add(session.session_id)
                for inf in session.inference_events:
                    total_cost += inf.cost_usd

        total_sessions = len(sessions)
        task_success_rate = completed / total_tasks if total_tasks else 0.0
        abandoned_rate = abandoned / total_sessions if total_sessions else 0.0
        avg_resolution = sum(resolution_times) / len(resolution_times) if resolution_times else 0.0
        cost_per_completed = total_cost / completed if completed else 0.0
        revenue_per_session = total_revenue / total_sessions if total_sessions else 0.0
        automation_rate = completed / total_tasks if total_tasks else 0.0
        error_rate = failed / total_tasks if total_tasks else 0.0

        retention_lift = None
        if baseline_retention_rate is not None and baseline_retention_rate > 0:
            # Simulated retention proxy: completed users retained at task_success_rate * 100
            observed_retention = task_success_rate * 100
            retention_lift = round((observed_retention - baseline_retention_rate) / baseline_retention_rate * 100, 2)

        return ExtrinsicMetrics(
            window_start=window_start,
            window_end=window_end,
            total_sessions=total_sessions,
            completed_tasks=completed,
            failed_tasks=failed,
            abandoned_tasks=abandoned,
            task_success_rate=round(task_success_rate, 4),
            user_abandoned_rate=round(abandoned_rate, 4),
            avg_time_to_resolution_sec=round(avg_resolution, 2),
            cost_per_completed_interaction_usd=round(cost_per_completed, 6),
            revenue_per_session_usd=round(revenue_per_session, 6),
            automation_rate=round(automation_rate, 4),
            error_rate=round(error_rate, 4),
            retention_lift_pct=retention_lift,
            total_cost_usd=round(total_cost, 6),
        )


class ContextualRecallCalculator:
    """
    Calcula métricas de recuperación contextual y coherencia multi-turno.
    """

    def calculate(
        self,
        sessions: List[UnifiedSession],
        window_start: float,
        window_end: float,
    ) -> ContextualRecallMetrics:
        total_inference = 0
        total_chunks = 0
        total_judge_scores = 0.0
        judge_count = 0
        sessions_with_context = 0

        multi_turn_scores: List[float] = []
        reference_scores: List[float] = []

        for session in sessions:
            inferences = sorted(session.inference_events, key=lambda x: x.timestamp)
            if inferences:
                total_inference += len(inferences)
                if any(inf.context_chunks_used > 0 or inf.context_references for inf in inferences):
                    sessions_with_context += 1
                for inf in inferences:
                    total_chunks += inf.context_chunks_used
                    if inf.llm_judge_context_score is not None:
                        total_judge_scores += inf.llm_judge_context_score
                        judge_count += 1

                # Multi-turn consistency: check if references are reused across turns
                references_per_turn = [set(inf.context_references) for inf in inferences]
                if len(references_per_turn) > 1:
                    overlaps = []
                    for i in range(1, len(references_per_turn)):
                        union = references_per_turn[i - 1] | references_per_turn[i]
                        inter = references_per_turn[i - 1] & references_per_turn[i]
                        overlaps.append(len(inter) / len(union) if union else 1.0)
                    multi_turn_scores.append(sum(overlaps) / len(overlaps))
                else:
                    multi_turn_scores.append(1.0)

                # Reference correctness: fraction of inferences that used expected refs
                if session.application_events:
                    expected_refs = set()
                    for app in session.application_events:
                        expected_refs.update(app.metadata.get("expected_references", []))
                    if expected_refs:
                        used_refs = set()
                        for inf in inferences:
                            used_refs.update(inf.context_references)
                        reference_scores.append(len(used_refs & expected_refs) / len(expected_refs))
                    else:
                        reference_scores.append(1.0)
                else:
                    reference_scores.append(1.0)

        avg_chunks = total_chunks / total_inference if total_inference else 0.0
        avg_judge = total_judge_scores / judge_count if judge_count else 0.0
        multi_turn = sum(multi_turn_scores) / len(multi_turn_scores) if multi_turn_scores else 0.0
        ref_correctness = sum(reference_scores) / len(reference_scores) if reference_scores else 0.0

        return ContextualRecallMetrics(
            window_start=window_start,
            window_end=window_end,
            avg_context_chunks_used=round(avg_chunks, 2),
            avg_llm_judge_context_score=round(avg_judge, 3),
            multi_turn_consistency_score=round(multi_turn, 3),
            reference_correctness_score=round(ref_correctness, 3),
            sessions_with_context=sessions_with_context,
            total_inference_events=total_inference,
        )
