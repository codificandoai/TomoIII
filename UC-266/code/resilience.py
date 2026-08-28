"""Motor de resiliencia y robustez para UC-266.

Funciones:
- Detectar cambios en el entorno comparando predicciones con observaciones reales.
- Generar planes de respaldo cuando falla una acción.
- Ejecutar bucles de autocorrección: detectar error, actualizar belief y replanificar.
- Evitar parálisis por análisis acotando intentos y presupuesto computacional.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from config import AppConfig, get_config
from models import ChangeEvent, PlanAction, RecoveryPlan, ResilienceLog, TravelPlanRequest, WorldModelState
from planner import PlanGenerator
from probabilistic_model import BeliefStateTracker
from world_model import TravelWorldModel


class ResilienceEngine:
    """Gestiona detección de cambios, planes de respaldo y bucles de autocorrección."""

    def __init__(
        self,
        world_model: TravelWorldModel,
        planner: PlanGenerator,
        config: AppConfig,
    ) -> None:
        self.world_model = world_model
        self.planner = planner
        self.config = config
        self.logs: List[ResilienceLog] = []
        self.recovery_attempts = 0
        self.belief_tracker = BeliefStateTracker(num_particles=100)

    def detect_change(
        self,
        action: PlanAction,
        predicted_success_prob: float,
        predicted_cost: float,
        observed_success: bool,
        actual_cost: float,
        observed_delay: float = 0.0,
    ) -> Optional[ChangeEvent]:
        """Detecta un cambio significativo entre predicción y realidad."""
        event = self.world_model.detect_change(
            action,
            predicted_success_prob,
            observed_success,
            predicted_cost,
            actual_cost,
            observed_delay,
        )
        if event:
            self.log("detect", f"Change detected: {event.event_type} for {action.item_id}", event.to_dict())
        return event

    def detect_planning_paralysis(
        self,
        candidates: List[Dict[str, Any]],
        elapsed_seconds: float,
        max_candidates: int = 100,
        max_time: float = 30.0,
    ) -> Optional[ChangeEvent]:
        """Detecta si el planificador está sobre-analizando sin decidir."""
        cfg = self.config.model.resilience
        if not cfg.enable:
            return None
        if elapsed_seconds > max_time or len(candidates) > max_candidates:
            event = ChangeEvent(
                event_type="planning_paralysis",
                severity=0.7,
                expected_impact="El planificador generó demasiados candidatos o tardó demasiado; se forzará decisión.",
                observed_data={"elapsed_seconds": elapsed_seconds, "num_candidates": len(candidates)},
            )
            self.log("diagnose", f"Planning paralysis detected: {len(candidates)} candidates, {elapsed_seconds:.2f}s", event.to_dict())
            return event
        return None

    def generate_backup_plans(
        self,
        request: TravelPlanRequest,
        initial_state: WorldModelState,
        failed_action: Optional[PlanAction] = None,
        rng: Optional[np.random.Generator] = None,
    ) -> Tuple[List[List[PlanAction]], Dict[str, Any]]:
        """Genera planes alternativos omitiendo la acción fallida."""
        rng = rng or np.random.default_rng()
        cfg = self.config.model.resilience
        if not cfg.enable:
            return [], {"reason": "resilience disabled"}

        # Aumentamos el número de candidatos para tener alternativas
        candidates, meta = self.planner.generate(
            request,
            num_plans=cfg.backup_plan_count * 3,
            world_model=self.world_model,
            initial_state=initial_state,
        )

        if failed_action:
            # Filtrar planes que contengan la acción fallida
            candidates = [
                plan for plan in candidates
                if not any(a.item_id == failed_action.item_id for a in plan)
            ]

        # Limitar a backup_plan_count
        backups = candidates[: cfg.backup_plan_count]
        self.log(
            "recover",
            f"Generated {len(backups)} backup plans",
            {"failed_action": failed_action.to_dict() if failed_action else None, "backups": len(backups)},
        )
        return backups, meta

    def execute_recovery_loop(
        self,
        request: TravelPlanRequest,
        initial_state: WorldModelState,
        actions: List[PlanAction],
        executor: Any,
        rng: Optional[np.random.Generator] = None,
    ) -> Tuple[WorldModelState, List[Dict[str, Any]], bool, List[ChangeEvent]]:
        """Ejecuta acciones y, si falla alguna, intenta recuperarse con planes de respaldo.

        Returns:
            (final_state, results, success, change_events)
        """
        rng = rng or np.random.default_rng()
        cfg = self.config.model.resilience
        state = initial_state.copy()
        results: List[Dict[str, Any]] = []
        change_events: List[ChangeEvent] = []
        max_attempts = cfg.max_recovery_attempts
        executed_ids: set[str] = set()

        for action in actions:
            # Evitar volver a ejecutar una acción ya probada
            if action.item_id in executed_ids:
                continue
            executed_ids.add(action.item_id)

            outcome = self._execute_action(executor, action)
            predicted_cost = action.estimated_cost
            actual_cost = outcome.get("actual_cost", predicted_cost)
            predicted_success_prob = action.estimated_success_prob
            observed_success = outcome.get("status") == "BOOKED"

            # Actualizar belief con observación ruidosa
            obs = self.world_model.observe(action.details, rng=rng)
            belief = BeliefStateTracker(num_particles=100).update(
                self._dict_to_belief(state.belief_state), obs, rng=rng
            )
            state.belief_state = belief.to_dict()

            event = self.detect_change(
                action,
                predicted_success_prob,
                predicted_cost,
                observed_success,
                actual_cost,
                obs.observed_delay,
            )
            if event:
                change_events.append(event)

            if observed_success:
                results.append({
                    "action_id": action.action_id,
                    "action_type": action.action_type,
                    "item_id": action.item_id,
                    "status": "BOOKED",
                    "cost": actual_cost,
                    "predicted_success_prob": predicted_success_prob,
                })
                state.total_cost += actual_cost
                if state.remaining_budget is not None:
                    state.remaining_budget -= actual_cost
            else:
                results.append({
                    "action_id": action.action_id,
                    "action_type": action.action_type,
                    "item_id": action.item_id,
                    "status": "FAILED",
                    "error": outcome.get("error"),
                    "predicted_success_prob": predicted_success_prob,
                })

                if not cfg.replan_after_failure:
                    return state, results, False, change_events

                # Intentar recuperación
                for attempt in range(1, max_attempts + 1):
                    backups, _ = self.generate_backup_plans(
                        request, state, failed_action=action, rng=rng
                    )
                    if not backups:
                        break
                    # Tomar el primer plan de respaldo y seguir ejecutando desde donde fallamos
                    backup = backups[0]
                    # Solo ejecutar acciones restantes no intentadas
                    remaining = [a for a in backup if a.item_id not in executed_ids]
                    if not remaining:
                        break
                    self.log(
                        "recover",
                        f"Recovery attempt {attempt}: switching to backup plan with {len(remaining)} remaining actions",
                        {"attempt": attempt},
                    )
                    recovered_state, recovered_results, recovered_success, recovered_events = self.execute_recovery_loop(
                        request, state, remaining, executor, rng=rng
                    )
                    results.extend(recovered_results)
                    change_events.extend(recovered_events)
                    if recovered_success:
                        return recovered_state, results, True, change_events
                    # Si falló, continuar intentando con otro backup
                return state, results, False, change_events

        return state, results, True, change_events

    def _execute_action(self, executor: Any, action: PlanAction) -> Dict[str, Any]:
        if action.action_type == "flight":
            return executor.book_flight(action.item_id)
        if action.action_type == "hotel":
            return executor.book_hotel(action.item_id)
        return {"status": "BOOKED", "actual_cost": action.estimated_cost}

    def _dict_to_belief(self, data: Optional[Dict[str, Any]]) -> Any:
        from models import BeliefState
        return BeliefState(**(data or {"particles": [], "weights": []}))

    def log(self, stage: str, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        self.logs.append(ResilienceLog(stage=stage, message=message, data=data or {}))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recovery_attempts": self.recovery_attempts,
            "logs": [log.to_dict() for log in self.logs[-50:]],
        }
