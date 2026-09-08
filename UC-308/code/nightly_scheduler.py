"""
UC-308 — Programador nocturno configurable y triggers por evento.

Soporta expresiones cron de 5 campos (minuto hora día-mes mes día-semana)
y ejecución inmediata por evento. Todo en memoria, sin cron externo.
"""

from __future__ import annotations

import time
from typing import List, Optional, Sequence, Tuple


class CronExpressionError(ValueError):
    pass


class NightlyScheduler:
    """
    Scheduler simple con soporte cron de 5 campos en UTC.
    """

    FIELD_NAMES = ["minute", "hour", "day", "month", "weekday"]
    FIELD_RANGES = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]

    def __init__(self, cron_expr: str = "0 2 * * *"):
        self.cron_expr = cron_expr
        self.fields = self._parse_cron(cron_expr)
        self.last_run_at: Optional[float] = None
        self.run_count: int = 0

    @staticmethod
    def _parse_field(value: str, min_v: int, max_v: int) -> set:
        if value == "*":
            return set(range(min_v, max_v + 1))
        result: set = set()
        for part in value.split(","):
            if "/" in part:
                step_part, step = part.split("/")
                step = int(step)
                if step_part == "*":
                    start, end = min_v, max_v
                elif "-" in step_part:
                    start, end = map(int, step_part.split("-"))
                else:
                    start = int(step_part)
                    end = max_v
                result.update(range(start, end + 1, step))
            elif "-" in part:
                start, end = map(int, part.split("-"))
                result.update(range(start, end + 1))
            else:
                result.add(int(part))
        return result

    def _parse_cron(self, expr: str) -> List[set]:
        parts = expr.strip().split()
        if len(parts) != 5:
            raise CronExpressionError(f"Invalid cron expression: {expr!r} (expected 5 fields)")
        fields = []
        for i, part in enumerate(parts):
            min_v, max_v = self.FIELD_RANGES[i]
            try:
                field = self._parse_field(part, min_v, max_v)
            except Exception as exc:
                raise CronExpressionError(f"Invalid cron field {self.FIELD_NAMES[i]}={part!r}: {exc}")
            fields.append(field)
        return fields

    def _matches(self, t: time.struct_time) -> bool:
        checks = [t.tm_min, t.tm_hour, t.tm_mday, t.tm_mon, t.tm_wday]
        return all(check in field for check, field in zip(checks, self.fields))

    def is_due(self, now: Optional[float] = None) -> bool:
        """Devuelve True si debe ejecutar y no se ha ejecutado ya en este minuto."""
        now = now or time.time()
        t = time.gmtime(now)
        if not self._matches(t):
            return False
        # Evitar múltiples ejecuciones dentro del mismo minuto.
        if self.last_run_at is not None:
            last_t = time.gmtime(self.last_run_at)
            if (
                t.tm_year == last_t.tm_year
                and t.tm_yday == last_t.tm_yday
                and t.tm_hour == last_t.tm_hour
                and t.tm_min == last_t.tm_min
            ):
                return False
        return True

    def mark_run(self, now: Optional[float] = None) -> None:
        self.last_run_at = now or time.time()
        self.run_count += 1

    def run_now(self, now: Optional[float] = None) -> float:
        """Trigger manual / por evento."""
        now = now or time.time()
        self.mark_run(now)
        return now

    def next_due_window(self, after: Optional[float] = None, max_search_minutes: int = 366 * 24 * 60) -> Optional[float]:
        """Busca el próximo timestamp en el que is_due sea True."""
        start = after or time.time()
        start_minute = int(start // 60) * 60
        for minute in range(0, max_search_minutes + 1):
            candidate = start_minute + minute * 60
            if candidate <= start:
                continue
            if self._matches(time.gmtime(candidate)):
                return candidate
        return None

    def to_dict(self) -> dict:
        return {
            "cron_expr": self.cron_expr,
            "last_run_at": self.last_run_at,
            "run_count": self.run_count,
            "fields": [sorted(f) for f in self.fields],
        }
