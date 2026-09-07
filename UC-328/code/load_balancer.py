"""
UC-328 — Balanceador de Carga para ORQUESTA-R.

Distribuye subconsultas entre fuentes según carga, latencia promedio,
confiabilidad y costo. Permite transferir tareas de fuentes sobrecargadas.
"""

from typing import List, Dict, Optional, Any

from orquesta_models import Source


class LoadBalancer:
    """
    Balancea carga entre fuentes de datos.

    Cada fuente mantiene una carga estimada. El balanceador selecciona
    la fuente con mejor score = confiabilidad / (carga + 1) / (latencia + 1) / (costo + 1).
    """

    def __init__(self):
        self._load: Dict[str, int] = {}

    def score_source(self, source: Source, avg_latency_ms: float = 200.0) -> float:
        """Calcula score de idoneidad de una fuente."""
        load = self._load.get(source.source_id, 0)
        latency = max(1.0, avg_latency_ms)
        cost = max(0.001, source.cost_per_call + 0.001)
        reliability = max(0.1, source.reliability)
        return reliability / ((load + 1) * latency * cost)

    def select_best(
        self,
        sources: List[Source],
        latency_map: Optional[Dict[str, float]] = None,
    ) -> Optional[Source]:
        """Selecciona la mejor fuente de una lista."""
        if not sources:
            return None
        latency_map = latency_map or {}
        scored = []
        for source in sources:
            latency = latency_map.get(source.source_id, source.base_latency_ms)
            score = self.score_source(source, latency)
            scored.append((score, source))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]

    def assign(self, source_id: str) -> None:
        """Incrementa carga asignada a una fuente."""
        self._load[source_id] = self._load.get(source_id, 0) + 1

    def release(self, source_id: str) -> None:
        """Decrementa carga asignada a una fuente."""
        self._load[source_id] = max(0, self._load.get(source_id, 0) - 1)

    def is_overloaded(self, source_id: str, threshold: int = 10) -> bool:
        """Determina si una fuente está sobrecargada."""
        return self._load.get(source_id, 0) >= threshold

    def rebalance_tasks(
        self,
        source_id: str,
        candidates: List[Source],
        threshold: int = 10,
    ) -> Optional[Source]:
        """
        Transfiere tarea de una fuente sobrecargada a la mejor candidata.

        Retorna la fuente alternativa o None si no hay opción.
        """
        if not self.is_overloaded(source_id, threshold):
            return None
        others = [s for s in candidates if s.source_id != source_id and s.enabled]
        return self.select_best(others)

    def get_statistics(self) -> Dict[str, Any]:
        """Retorna estadísticas de carga."""
        total_load = sum(self._load.values())
        return {
            "total_assigned_load": total_load,
            "sources_tracked": len(self._load),
            "loads": dict(self._load),
        }

    def reset(self) -> None:
        """Limpia cargas."""
        self._load.clear()
