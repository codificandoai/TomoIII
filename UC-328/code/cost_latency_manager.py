"""
UC-328 — Gestor de Costo y Latencia para ORQUESTA-R.

Estima, rastrea y controla presupuestos monetarios y temporales.
Incluye estimación histórica, control de concurrencia y detección de
exceso de presupuesto.
"""

from typing import Dict, List, Optional, Any
import time

from orquesta_models import Source, Subquery, Budget, ExecutionMetrics


class CostLatencyManager:
    """
    Gestiona presupuestos y estimaciones de costo/latencia.

    Mantiene histórico por fuente para mejorar estimaciones futuras.
    """

    def __init__(self, budget: Optional[Budget] = None):
        self.budget = budget or Budget()
        self._spent_cost: float = 0.0
        self._spent_latency_ms: float = 0.0
        self._running_calls: int = 0
        self._history: Dict[str, List[Dict[str, float]]] = {}

    def estimate(self, source: Source, subquery: Subquery, data_size_kb: float = 1.0) -> Dict[str, float]:
        """
        Estima costo y latencia para ejecutar una subconsulta en una fuente.

        Usa histórico si existe; de lo contrario, baseline.
        """
        key = source.source_id
        records = self._history.get(key, [])

        if records:
            avg_cost = sum(r["cost"] for r in records) / len(records)
            p90_latency = sorted(r["latency_ms"] for r in records)[int(len(records) * 0.9)] if len(records) > 1 else records[0]["latency_ms"]
            cost = avg_cost * self._peak_factor()
            latency = p90_latency * self._peak_factor()
        else:
            cost = source.cost_per_call + (source.cost_per_kb * data_size_kb)
            latency = source.base_latency_ms + (subquery.text.count(" ") * 10)  # simple complexity proxy

        return {
            "estimated_cost": round(cost, 6),
            "estimated_latency_ms": round(latency, 2),
        }

    def _peak_factor(self) -> float:
        """Factor multiplicador conservador según carga actual."""
        load = self._running_calls / max(1, self.budget.max_concurrent_calls)
        return 1.0 + min(0.5, load * 0.5)

    def can_afford(self, estimated_cost: float, estimated_latency_ms: float) -> bool:
        """Verifica si queda presupuesto para una operación."""
        if self._spent_cost + estimated_cost > self.budget.max_cost:
            return False
        if self._spent_latency_ms + estimated_latency_ms > self.budget.max_latency_ms:
            return False
        if self._running_calls >= self.budget.max_concurrent_calls:
            return False
        return True

    def start_call(self) -> bool:
        """Incrementa contador de llamadas concurrentes."""
        if self._running_calls >= self.budget.max_concurrent_calls:
            return False
        self._running_calls += 1
        return True

    def end_call(self) -> None:
        """Decrementa contador de llamadas concurrentes."""
        self._running_calls = max(0, self._running_calls - 1)

    def record_actual(
        self,
        source_id: str,
        cost: float,
        latency_ms: float,
        success: bool,
    ) -> None:
        """Registra costo y latencia reales para estimaciones futuras."""
        self._spent_cost += cost
        self._spent_latency_ms += latency_ms
        if success:
            self._history.setdefault(source_id, []).append({
                "cost": cost,
                "latency_ms": latency_ms,
                "timestamp": time.time(),
            })
            # Keep only last 100 records
            if len(self._history[source_id]) > 100:
                self._history[source_id] = self._history[source_id][-100:]

    def get_remaining_budget(self) -> Dict[str, float]:
        """Retorna presupuesto restante."""
        return {
            "remaining_cost": max(0.0, self.budget.max_cost - self._spent_cost),
            "remaining_latency_ms": max(0.0, self.budget.max_latency_ms - self._spent_latency_ms),
            "remaining_concurrent": max(0, self.budget.max_concurrent_calls - self._running_calls),
        }

    def get_history(self, source_id: Optional[str] = None) -> Dict[str, List[Dict[str, float]]]:
        """Retorna histórico de ejecuciones."""
        if source_id:
            return {source_id: list(self._history.get(source_id, []))}
        return {k: list(v) for k, v in self._history.items()}

    def get_statistics(self) -> Dict[str, Any]:
        """Retorna estadísticas del gestor."""
        return {
            "spent_cost": round(self._spent_cost, 6),
            "spent_latency_ms": round(self._spent_latency_ms, 2),
            "running_calls": self._running_calls,
            "budget": self.budget.to_dict(),
            "remaining": self.get_remaining_budget(),
            "sources_with_history": list(self._history.keys()),
        }

    def reset(self) -> None:
        """Resetea presupuesto e histórico."""
        self._spent_cost = 0.0
        self._spent_latency_ms = 0.0
        self._running_calls = 0
        self._history.clear()
