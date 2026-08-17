"""UC-700 — Motor de diagnóstico y clasificación de fallos.

Paso 2: Clasificar el fallo.
Distingue entre: hardware, transitorio, driver, red, térmico, storage,
contenedor, código de entrenamiento, deterioro del modelo, datos.
"""

from __future__ import annotations

from typing import Dict, List

from config import FailureClass, HealthState
from models import AnomalySignal, Diagnosis, Device, Node, TelemetrySnapshot


class DiagnosticAgent:
    """Paso 2: Clasificar el fallo con evidencia multiseñal."""

    def __init__(self, min_evidence_signals: int = 2):
        self.min_evidence_signals = min_evidence_signals

    def diagnose(
        self,
        node: Node,
        snapshot: TelemetrySnapshot,
        signal: AnomalySignal,
    ) -> Diagnosis:
        evidence: List[Dict[str, str]] = []
        scores: Dict[str, float] = {cls: 0.0 for cls in self._classes()}

        temp = snapshot.metrics.get("DCGM_FI_DEV_GPU_TEMP", 0.0)
        vram_used = snapshot.metrics.get("DCGM_FI_DEV_FB_USED", 0.0)
        vram_total = snapshot.metrics.get("DCGM_FI_DEV_FB_TOTAL", 1.0)
        vram_pct = vram_used / vram_total * 100
        xid = snapshot.metrics.get("DCGM_FI_DEV_XID_ERRORS", 0.0)
        pcie_replay = snapshot.metrics.get("DCGM_FI_DEV_PCIE_REPLAY", 0.0)
        net_drop = snapshot.metrics.get("node_network_transmit_drop_total", 0.0)
        util = snapshot.metrics.get("DCGM_FI_DEV_GPU_UTIL", 0.0)
        loss = snapshot.metrics.get("training_loss", 0.0)
        step_time = snapshot.metrics.get("training_step_time_ms", 0.0)

        # Hardware / memoria (prioridad cuando hay XID o VRAM crítica)
        if xid > 0 or vram_pct > 95:
            scores[FailureClass.HARDWARE] += 2.0
            evidence.append({"class": FailureClass.HARDWARE, "reason": f"XID errors={int(xid)}, VRAM pressure={vram_pct:.1f}%"})

        # Térmico
        if temp > 85 and xid == 0:
            scores[FailureClass.THERMAL] += 1.0 + (temp - 85) / 20
            evidence.append({"class": FailureClass.THERMAL, "reason": f"GPU temperature={temp:.1f}C"})

        # Red
        if net_drop > 1.0:
            scores[FailureClass.NETWORK] += 1.0
            evidence.append({"class": FailureClass.NETWORK, "reason": f"Network drops={net_drop:.1f}"})

        # Driver / PCIe
        if pcie_replay > 50:
            scores[FailureClass.DRIVER] += 0.8
            evidence.append({"class": FailureClass.DRIVER, "reason": f"PCIe replays={pcie_replay:.1f}"})

        # Contenedor / runtime
        if util < 10 and step_time > 200:
            scores[FailureClass.CONTAINER] += 0.7
            evidence.append({"class": FailureClass.CONTAINER, "reason": f"Low GPU util={util:.1f}% with high step_time={step_time:.1f}ms"})

        # Código de entrenamiento
        if step_time > 300 and util > 50:
            scores[FailureClass.TRAINING_CODE] += 0.5
            evidence.append({"class": FailureClass.TRAINING_CODE, "reason": f"High step_time={step_time:.1f}ms despite util={util:.1f}%"})

        # Deterioro del modelo
        if loss > 5.0:
            scores[FailureClass.MODEL_DEGRADATION] += 0.6
            evidence.append({"class": FailureClass.MODEL_DEGRADATION, "reason": f"Loss spike={loss:.3f}"})

        # Datos
        if loss == 0.0 and step_time == 0.0:
            scores[FailureClass.DATA_ISSUE] += 0.3
            evidence.append({"class": FailureClass.DATA_ISSUE, "reason": "Missing training metrics"})

        # Si no hay señal fuerte, se considera transitorio o desconocido
        max_score = max(scores.values())
        if max_score == 0.0:
            failure_class = FailureClass.TRANSIENT
            evidence.append({"class": failure_class, "reason": "No strong failure signature; treat as transient"})
        else:
            failure_class = max(scores, key=scores.get)  # type: ignore[arg-type]

        suspected_devices = [d.id for d in node.devices if d.state != HealthState.HEALTHY]
        if snapshot.device_id:
            suspected_devices.append(snapshot.device_id)
        suspected_devices = list(set(suspected_devices))

        confidence = min(1.0, len(evidence) / max(1, self.min_evidence_signals))

        return Diagnosis(
            failure_class=failure_class,
            evidence=evidence,
            confidence=round(confidence, 4),
            suspected_devices=suspected_devices,
            recommendation=self._recommend(failure_class),
        )

    def _classes(self) -> List[str]:
        return [
            FailureClass.HARDWARE,
            FailureClass.TRANSIENT,
            FailureClass.DRIVER,
            FailureClass.NETWORK,
            FailureClass.THERMAL,
            FailureClass.STORAGE,
            FailureClass.CONTAINER,
            FailureClass.TRAINING_CODE,
            FailureClass.MODEL_DEGRADATION,
            FailureClass.DATA_ISSUE,
            FailureClass.UNKNOWN,
        ]

    def _recommend(self, failure_class: str) -> str:
        recommendations = {
            FailureClass.HARDWARE: "Quarantine device and plan replacement",
            FailureClass.THERMAL: "Throttle workload and check cooling",
            FailureClass.NETWORK: "Migrate to node with healthy fabric",
            FailureClass.DRIVER: "Reset driver or rolling update",
            FailureClass.TRANSIENT: "Retry and observe before isolation",
            FailureClass.CONTAINER: "Restart container preserving checkpoint",
            FailureClass.TRAINING_CODE: "Escalate to ML engineer",
            FailureClass.MODEL_DEGRADATION: "Rollback to previous checkpoint",
            FailureClass.DATA_ISSUE: "Validate data pipeline",
            FailureClass.UNKNOWN: "Escalate to operator",
        }
        return recommendations.get(failure_class, "Escalate to operator")
