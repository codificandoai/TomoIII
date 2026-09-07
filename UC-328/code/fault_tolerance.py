"""
UC-328 — Tolerancia a Fallos para ORQUESTA-R.

Implementa circuit breakers, reintentos con backoff exponencial,
agentes sustitutos y modos degradados.
"""

from typing import Dict, Optional, Any, Tuple, Callable
import time

from orquesta_models import Source, HealthStatus


class FaultToleranceManager:
    """
    Gestiona tolerancia a fallos en fuentes externas y agentes.

    Reglas:
    - Tras N fallos consecutivos, abre circuit breaker por un tiempo.
    - Reintentos con backoff exponencial.
    - Fallback a cache, fuente secundaria o estimación.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        circuit_breaker_seconds: float = 300.0,
        max_retries: int = 2,
        base_backoff_ms: float = 500.0,
    ):
        self.failure_threshold = failure_threshold
        self.circuit_breaker_seconds = circuit_breaker_seconds
        self.max_retries = max_retries
        self.base_backoff_ms = base_backoff_ms
        self._health: Dict[str, HealthStatus] = {}

    def get_health(self, source_id: str) -> HealthStatus:
        """Obtiene o crea el estado de salud de una fuente."""
        if source_id not in self._health:
            self._health[source_id] = HealthStatus(source_id=source_id)
        return self._health[source_id]

    def is_available(self, source_id: str) -> bool:
        """Verifica si una fuente está disponible (circuit breaker cerrado)."""
        health = self.get_health(source_id)
        return not health.is_circuit_open

    def record_success(self, source_id: str, latency_ms: float) -> None:
        """Registra una ejecución exitosa."""
        health = self.get_health(source_id)
        health.consecutive_failures = 0
        health.healthy = True
        health.circuit_open_until = None
        health.avg_latency_ms = self._ewma(health.avg_latency_ms, latency_ms)
        health.load = max(0, health.load - 1)

    def record_failure(
        self,
        source_id: str,
        error: Optional[str] = None,
        overload: bool = False,
    ) -> bool:
        """
        Registra un fallo y decide si abrir circuit breaker.

        Retorna True si el circuit breaker se abrió.
        """
        health = self.get_health(source_id)
        health.consecutive_failures += 1
        health.last_failure_time = time.time()
        health.load = max(0, health.load - 1)
        if overload:
            health.healthy = False

        if health.consecutive_failures >= self.failure_threshold:
            health.circuit_open_until = time.time() + self.circuit_breaker_seconds
            return True
        return False

    def record_overload(self, source_id: str) -> None:
        """Registra sobrecarga en una fuente."""
        self.record_failure(source_id, overload=True)

    def _ewma(self, current: float, new_value: float, alpha: float = 0.3) -> float:
        """Media móvil exponencial."""
        if current == 0:
            return new_value
        return alpha * new_value + (1 - alpha) * current

    def backoff_ms(self, attempt: int) -> float:
        """Calcula backoff exponencial para un intento."""
        return self.base_backoff_ms * (2 ** attempt)

    def execute_with_retry(
        self,
        source_id: str,
        operation: Callable[[], Any],
        fallback: Optional[Callable[[], Any]] = None,
    ) -> Tuple[Any, bool, int]:
        """
        Ejecuta una operación con reintentos.

        Retorna (resultado, éxito, intentos_usados).
        """
        if not self.is_available(source_id):
            if fallback:
                return fallback(), True, 0
            return None, False, 0

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                result = operation()
                return result, True, attempt + 1
            except Exception as e:
                last_error = e
                is_overload = self._is_overload(str(e))
                circuit_opened = self.record_failure(source_id, str(e), overload=is_overload)
                if circuit_opened:
                    break
                if attempt < self.max_retries:
                    wait_ms = self.backoff_ms(attempt)
                    time.sleep(wait_ms / 1000.0)
        # All retries failed
        if fallback:
            return fallback(), True, self.max_retries + 1
        return None, False, self.max_retries + 1

    def _is_overload(self, error_message: str) -> bool:
        """Heurística para detectar sobrecarga."""
        overload_terms = ["timeout", "rate limit", "overload", "too many", "503", "429", "slow"]
        return any(term in error_message.lower() for term in overload_terms)

    def get_statistics(self) -> Dict[str, Any]:
        """Retorna estadísticas de salud."""
        return {
            "total_sources": len(self._health),
            "healthy": sum(1 for h in self._health.values() if h.healthy and not h.is_circuit_open),
            "unhealthy": sum(1 for h in self._health.values() if not h.healthy),
            "circuit_open": sum(1 for h in self._health.values() if h.is_circuit_open),
            "details": {k: v.to_dict() for k, v in self._health.items()},
        }

    def reset(self) -> None:
        """Limpia estado de salud."""
        self._health.clear()
