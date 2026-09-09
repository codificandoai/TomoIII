"""Motor de SLOs, SLIs y presupuestos de error."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from incident_management.models_incident import ErrorBudget, SLODefinition, SLIDefinition


class SLOEngine:
    """
    Mantiene definiciones de SLIs y SLOs, consume presupuestos de error y
    calcula burn rate.
    """

    def __init__(self) -> None:
        self._slis: Dict[str, SLIDefinition] = {}
        self._slos: Dict[str, SLODefinition] = {}
        self._samples: Dict[str, List[Dict[str, Any]]] = {}

    def register_sli(self, sli_id: str, name: str, metric: str, unit: str, description: str = "") -> SLIDefinition:
        sli = SLIDefinition(sli_id=sli_id, name=name, metric=metric, unit=unit, description=description)
        self._slis[sli_id] = sli
        return sli

    def define_slo(
        self,
        sli_id: str,
        target: float,
        window_seconds: float,
        description: str = "",
    ) -> Optional[SLODefinition]:
        if sli_id not in self._slis:
            return None
        slo = SLODefinition(sli_id=sli_id, target=target, window_seconds=window_seconds, description=description)
        self._slos[slo.slo_id] = slo
        return slo

    def record_sample(self, slo_id: str, good: bool, timestamp: Optional[float] = None) -> None:
        if slo_id not in self._slos:
            return
        ts = timestamp or time.time()
        self._samples.setdefault(slo_id, []).append({"good": good, "timestamp": ts})

    def compute_error_budget(self, slo_id: str, now: Optional[float] = None) -> Optional[ErrorBudget]:
        slo = self._slos.get(slo_id)
        if not slo:
            return None
        now = now or time.time()
        window_start = now - slo.window_seconds
        samples = [s for s in self._samples.get(slo_id, []) if s["timestamp"] >= window_start]
        total = len(samples)
        good = sum(1 for s in samples if s["good"])
        bad = total - good
        total_budget = slo.error_budget() * total if total else 0.0
        consumed = bad  # each bad event consumes 1 unit in a ratio metric
        remaining = total_budget - consumed
        hours = slo.window_seconds / 3600.0
        burn_rate = consumed / hours if hours else 0.0
        return ErrorBudget(
            slo_id=slo_id,
            window_start=window_start,
            window_end=now,
            total_budget=round(total_budget, 4),
            consumed=consumed,
            remaining=round(remaining, 4),
            burn_rate=round(burn_rate, 6),
        )

    def list_slos(self) -> List[SLODefinition]:
        return list(self._slos.values())
