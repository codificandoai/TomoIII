"""
UC-308 — Alert Manager en memoria.

Implementa ventanas móviles, histéresis y fallos consecutivos para evitar
fatiga de alertas. No envía notificaciones externas; emite recomendaciones.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional, Sequence, Tuple

from mitigation_advisor import MitigationAdvisor
from models_308 import (
    Alert,
    DriftConfig,
    DriftSignal,
    DriftStatus,
    EvaluationRun,
    Recommendation,
    SystemStatus,
)


class AlertManager:
    """
    Mantiene el histórico de evaluaciones y emite alertas solo cuando una
    condición se sostiene durante N ejecuciones consecutivas (hysteresis).
    """

    def __init__(self, advisor: Optional[MitigationAdvisor] = None):
        self.advisor = advisor or MitigationAdvisor()
        self.alerts: List[Alert] = []
        self.run_history: List[Tuple[str, float, SystemStatus]] = []
        # Última alerta emitida por nivel (degraded/critical) para evitar duplicados.
        self._last_alert_for: Dict[SystemStatus, int] = {}

    @staticmethod
    def _status_order(status: SystemStatus) -> int:
        mapping = {
            SystemStatus.NORMAL: 0,
            SystemStatus.WARNING: 1,
            SystemStatus.DEGRADED: 2,
            SystemStatus.CRITICAL: 3,
        }
        return mapping.get(status, 0)

    def _system_status_from_signals(self, signals: Sequence[DriftSignal]) -> SystemStatus:
        if not signals:
            return SystemStatus.NORMAL
        order = 0
        for s in signals:
            order = max(order, self._status_order(SystemStatus(s.status.value)))
        return SystemStatus([SystemStatus.NORMAL, SystemStatus.WARNING, SystemStatus.DEGRADED, SystemStatus.CRITICAL][order])

    def _consecutive_count(self, min_status: SystemStatus) -> int:
        """Cuenta ejecuciones consecutivas con estado >= min_status."""
        target = self._status_order(min_status)
        count = 0
        for _, _, status in reversed(self.run_history):
            if self._status_order(status) >= target:
                count += 1
            else:
                break
        return count

    def evaluate_run(
        self,
        run: EvaluationRun,
        signals: Sequence[DriftSignal],
        config: DriftConfig,
    ) -> Tuple[SystemStatus, List[Alert]]:
        """
        Evalúa una corrida y emite alertas si las ventanas/histéresis lo indican.
        """
        system_status = self._system_status_from_signals(signals)
        self.run_history.append((run.run_id, run.timestamp, system_status))
        if len(self.run_history) > config.window_size:
            self.run_history.pop(0)

        new_alerts: List[Alert] = []

        if system_status == SystemStatus.NORMAL:
            consecutive_normal = 0
            for _, _, status in reversed(self.run_history):
                if status == SystemStatus.NORMAL:
                    consecutive_normal += 1
                else:
                    break
            if consecutive_normal >= config.consecutive_normal_to_resolve:
                resolved_at = time.time()
                for alert in self.alerts:
                    if not alert.resolved:
                        alert.resolved = True
                        alert.resolved_at = resolved_at

        # Critical: alertar inmediatamente si se alcanza el umbral consecutivo.
        # Incluimos señales degraded junto a critical para que las recomendaciones
        # cubran también la causa subyacente (p. ej. contract drift crítico).
        if system_status == SystemStatus.CRITICAL:
            if self._consecutive_count(SystemStatus.CRITICAL) >= config.consecutive_critical_to_alert:
                alert_signals = [s for s in signals if s.status in (DriftStatus.CRITICAL, DriftStatus.DEGRADED)]
                alert = self._build_alert(run, alert_signals, system_status)
                if self._register_alert(alert):
                    new_alerts.append(alert)

        # Degraded: requiere N consecutivas para alertar.
        if system_status == SystemStatus.DEGRADED:
            if self._consecutive_count(SystemStatus.DEGRADED) >= config.consecutive_degraded_to_alert:
                degraded_signals = [s for s in signals if s.status in (DriftStatus.DEGRADED, DriftStatus.CRITICAL)]
                alert = self._build_alert(run, degraded_signals, system_status)
                if self._register_alert(alert):
                    new_alerts.append(alert)

        # Warning: se alerta en la primera ocurrencia (pero no repite si ya hay
        # alerta warning activa no reconocida). Se emite como recomendación suave.
        if system_status == SystemStatus.WARNING and not any(
            a.status == DriftStatus.WARNING and not a.acknowledged and not a.resolved
            for a in self.alerts
        ):
            warning_signals = [s for s in signals if s.status == DriftStatus.WARNING]
            if warning_signals:
                alert = self._build_alert(run, warning_signals, system_status)
                if self._register_alert(alert):
                    new_alerts.append(alert)

        run.system_status = system_status
        run.alert_ids.extend([a.alert_id for a in new_alerts])
        return system_status, new_alerts

    def _register_alert(self, alert: Alert) -> bool:
        """Evita duplicar alertas idénticas del mismo run y nivel."""
        key = alert.status
        if key in self._last_alert_for and self._last_alert_for[key] == alert.run_id:
            return False
        self._last_alert_for[key] = alert.run_id
        self.alerts.append(alert)
        return True

    def _build_alert(
        self,
        run: EvaluationRun,
        signals: Sequence[DriftSignal],
        system_status: SystemStatus,
    ) -> Alert:
        drift_type_set = set(s.drift_type.value for s in signals)
        recommendations = self.advisor.recommend(
            system_status=system_status,
            signals=signals,
            affected_tools=list(set(s.evidence.get("tool", run.results[0].tool if run.results else "unknown") for s in signals)),
        )
        messages = []
        for s in signals:
            messages.append(f"[{s.drift_type.value}] {s.message}")
        message = " | ".join(messages) or f"System status is {system_status.value}"

        return Alert(
            alert_id=f"alert-{uuid.uuid4().hex[:8]}",
            timestamp=time.time(),
            run_id=run.run_id,
            status=DriftStatus(system_status.value),
            drift_signal_ids=[s.signal_id for s in signals],
            system_status=system_status,
            recommendations=recommendations,
            message=message,
        )

    def get_active_alerts(self) -> List[Alert]:
        return [a for a in self.alerts if not a.acknowledged and not a.resolved]

    def acknowledge(self, alert_id: str) -> bool:
        for alert in self.alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alerts": [a.to_dict() for a in self.alerts],
            "active_count": len(self.get_active_alerts()),
            "history": [
                {"run_id": rid, "timestamp": ts, "status": st.value}
                for rid, ts, st in self.run_history
            ],
        }

    def reset(self) -> None:
        self.alerts.clear()
        self.run_history.clear()
        self._last_alert_for.clear()
