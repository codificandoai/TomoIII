"""UC-324 — Monitoreo safety-critical inspirado en awesome-safety-critical-ai (E).

El recurso `JGalego/awesome-safety-critical-ai` es una lista curada de papers,
herramientas y frameworks; no es una librería instalable. UC-324 implementa aquí
los patrones clave extraídos de esa lista:

- Circuit breakers por skill con estados CLOSED, OPEN, HALF_OPEN.
- Umbrales de confianza: si una predicción/skill tiene confianza baja, se rechaza.
- Monitoreo de latencia y coste: acciones fuera de límites de diseño se bloquean.
- Tasas de fallo y éxito por ventana deslizante para decidir apertura del breaker.
- Recuperación automática en HALF_OPEN para probar de nuevo tras un cooldown.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class CircuitState(str, Enum):
    CLOSED = "closed"       # Funcionamiento normal
    OPEN = "open"           # Bloqueando llamadas
    HALF_OPEN = "half_open" # Prueba de recuperación


@dataclass
class SkillMetrics:
    """Métricas acumuladas para una skill."""

    successes: int = 0
    failures: int = 0
    total_latency_ms: float = 0.0
    total_cost: float = 0.0
    min_confidence_seen: float = 1.0
    last_seen: float = 0.0
    samples: List[Dict[str, Any]] = field(default_factory=list)

    def success_rate(self, window: int = 100) -> float:
        recent = self.samples[-window:]
        if not recent:
            return 1.0
        return sum(1 for s in recent if s.get("success")) / len(recent)

    def avg_latency_ms(self, window: int = 100) -> float:
        recent = self.samples[-window:]
        if not recent:
            return 0.0
        return sum(s.get("latency_ms", 0.0) for s in recent) / len(recent)

    def avg_cost(self, window: int = 100) -> float:
        recent = self.samples[-window:]
        if not recent:
            return 0.0
        return sum(s.get("cost", 0.0) for s in recent) / len(recent)


@dataclass
class CircuitBreakerConfig:
    """Configuración de un circuit breaker."""

    failure_threshold: int = 3
    success_rate_threshold: float = 0.5
    recovery_timeout_seconds: float = 10.0
    half_open_max_calls: int = 2
    max_latency_ms: Optional[float] = None
    max_cost: Optional[float] = None
    min_confidence: Optional[float] = None


@dataclass
class CircuitBreakerState:
    """Estado actual de un circuit breaker."""

    skill_name: str
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[float] = None
    opened_at: Optional[float] = None
    half_open_calls: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_name": self.skill_name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "opened_at": self.opened_at,
            "half_open_calls": self.half_open_calls,
        }


class SafetyCriticalMonitor:
    """Monitor safety-critical con circuit breakers y umbrales de confianza."""

    DEFAULT_BREAKER_CONFIG = CircuitBreakerConfig(
        failure_threshold=3,
        success_rate_threshold=0.5,
        recovery_timeout_seconds=10.0,
        half_open_max_calls=2,
    )

    def __init__(
        self,
        configs: Optional[Dict[str, CircuitBreakerConfig]] = None,
        default_config: Optional[CircuitBreakerConfig] = None,
        sample_window: int = 100,
    ) -> None:
        self.configs = configs or {}
        self.default_config = default_config or self.DEFAULT_BREAKER_CONFIG
        self.sample_window = sample_window
        self._metrics: Dict[str, SkillMetrics] = {}
        self._breakers: Dict[str, CircuitBreakerState] = {}

    def _config_for(self, skill_name: str) -> CircuitBreakerConfig:
        return self.configs.get(skill_name, self.default_config)

    def _breaker_for(self, skill_name: str) -> CircuitBreakerState:
        if skill_name not in self._breakers:
            self._breakers[skill_name] = CircuitBreakerState(skill_name=skill_name)
        return self._breakers[skill_name]

    def _metrics_for(self, skill_name: str) -> SkillMetrics:
        if skill_name not in self._metrics:
            self._metrics[skill_name] = SkillMetrics()
        return self._metrics[skill_name]

    def record(
        self,
        skill_name: str,
        success: bool,
        latency_ms: float = 0.0,
        cost: float = 0.0,
        confidence: Optional[float] = None,
    ) -> None:
        """Registra una observación de ejecución de una skill."""
        metrics = self._metrics_for(skill_name)
        ts = time.time()
        sample = {
            "success": success,
            "latency_ms": latency_ms,
            "cost": cost,
            "confidence": confidence,
            "timestamp": ts,
        }
        metrics.samples.append(sample)
        if len(metrics.samples) > self.sample_window:
            metrics.samples.pop(0)
        metrics.last_seen = ts
        metrics.total_latency_ms += latency_ms
        metrics.total_cost += cost
        if confidence is not None and confidence < metrics.min_confidence_seen:
            metrics.min_confidence_seen = confidence

        if success:
            metrics.successes += 1
        else:
            metrics.failures += 1

        self._update_breaker(skill_name, sample)

    def _update_breaker(self, skill_name: str, sample: Dict[str, Any]) -> None:
        breaker = self._breaker_for(skill_name)
        config = self._config_for(skill_name)
        now = time.time()

        if breaker.state == CircuitState.OPEN:
            # Verificar si ha pasado el cooldown para intentar half-open
            if (
                breaker.opened_at is not None
                and now - breaker.opened_at >= config.recovery_timeout_seconds
            ):
                breaker.state = CircuitState.HALF_OPEN
                breaker.half_open_calls = 0
            else:
                return

        if breaker.state == CircuitState.HALF_OPEN:
            breaker.half_open_calls += 1
            if sample["success"]:
                breaker.success_count += 1
                if breaker.success_count >= config.half_open_max_calls:
                    breaker.state = CircuitState.CLOSED
                    breaker.failure_count = 0
                    breaker.success_count = 0
                    breaker.half_open_calls = 0
                    breaker.opened_at = None
            else:
                breaker.state = CircuitState.OPEN
                breaker.opened_at = now
                breaker.last_failure_time = now
                breaker.half_open_calls = 0
                breaker.success_count = 0
            return

        # CLOSED
        if not sample["success"]:
            breaker.failure_count += 1
            breaker.last_failure_time = now
            if breaker.failure_count >= config.failure_threshold:
                breaker.state = CircuitState.OPEN
                breaker.opened_at = now
        else:
            breaker.failure_count = 0

    def can_execute(
        self,
        skill_name: str,
        latency_ms: Optional[float] = None,
        cost: Optional[float] = None,
        confidence: Optional[float] = None,
    ) -> Tuple[bool, List[str]]:
        """Determina si se puede ejecutar una skill según circuit breaker y umbrales.

        Returns:
            (allowed, issues)
        """
        breaker = self._breaker_for(skill_name)
        config = self._config_for(skill_name)
        issues: List[str] = []

        now = time.time()
        if breaker.state == CircuitState.OPEN:
            if (
                breaker.opened_at is not None
                and now - breaker.opened_at >= config.recovery_timeout_seconds
            ):
                breaker.state = CircuitState.HALF_OPEN
                breaker.half_open_calls = 0
            else:
                issues.append(
                    f"Circuit breaker OPEN for {skill_name}: too many recent failures"
                )
                return False, issues

        if breaker.state == CircuitState.HALF_OPEN:
            if breaker.half_open_calls >= config.half_open_max_calls:
                issues.append(
                    f"Circuit breaker HALF_OPEN for {skill_name}: max test calls reached"
                )
                return False, issues

        if latency_ms is not None and config.max_latency_ms is not None:
            if latency_ms > config.max_latency_ms:
                issues.append(
                    f"Latency {latency_ms}ms exceeds design limit {config.max_latency_ms}ms for {skill_name}"
                )

        if cost is not None and config.max_cost is not None:
            if cost > config.max_cost:
                issues.append(
                    f"Cost {cost} exceeds design limit {config.max_cost} for {skill_name}"
                )

        if confidence is not None and config.min_confidence is not None:
            if confidence < config.min_confidence:
                issues.append(
                    f"Confidence {confidence} below threshold {config.min_confidence} for {skill_name}"
                )

        return len(issues) == 0, issues

    def status(self) -> Dict[str, Any]:
        """Devuelve el estado completo del monitor."""
        return {
            "breakers": {name: cb.to_dict() for name, cb in self._breakers.items()},
            "metrics": {
                name: {
                    "success_rate": m.success_rate(),
                    "avg_latency_ms": m.avg_latency_ms(),
                    "avg_cost": m.avg_cost(),
                    "min_confidence_seen": m.min_confidence_seen,
                    "successes": m.successes,
                    "failures": m.failures,
                }
                for name, m in self._metrics.items()
            },
        }

    def manual_trip(self, skill_name: str) -> None:
        """Abre manualmente el circuit breaker de una skill (kill-switch auxiliar)."""
        breaker = self._breaker_for(skill_name)
        breaker.state = CircuitState.OPEN
        breaker.opened_at = time.time()
        breaker.last_failure_time = time.time()
        breaker.failure_count += 1

    def manual_reset(self, skill_name: str) -> None:
        """Cierra manualmente el circuit breaker de una skill."""
        breaker = self._breaker_for(skill_name)
        breaker.state = CircuitState.CLOSED
        breaker.failure_count = 0
        breaker.success_count = 0
        breaker.half_open_calls = 0
        breaker.opened_at = None


# Helper de alto nivel para integración

def default_monitor_for_critical_skills() -> SafetyCriticalMonitor:
    """Crea un monitor con umbrales ajustados para skills críticas."""
    return SafetyCriticalMonitor(
        configs={
            "PaymentSkill": CircuitBreakerConfig(
                failure_threshold=2,
                recovery_timeout_seconds=5.0,
                max_latency_ms=2000.0,
                max_cost=5.0,
                min_confidence=0.8,
            ),
            "MarketExecutionSkill": CircuitBreakerConfig(
                failure_threshold=2,
                recovery_timeout_seconds=5.0,
                max_latency_ms=50.0,
                max_cost=10.0,
                min_confidence=0.85,
            ),
            "ChangeCancelSkill": CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout_seconds=10.0,
                max_latency_ms=2000.0,
                max_cost=5.0,
                min_confidence=0.7,
            ),
        }
    )
