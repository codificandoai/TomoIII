"""UC-700 — Agente de detección de anomalías.

Combina:
  - Umbrales estáticos
  - Detección de anomalías estadística (z-score / IQR)
  - Comparación con nodos homólogos
  - Análisis de cambios
"""

from __future__ import annotations

import statistics
from datetime import datetime
from typing import Dict, List, Optional

from config import AgentConfig, HealthState, SeverityLevel
from models import AnomalySignal, Node, TelemetrySnapshot


class AnomalyDetectionAgent:
    """Paso 1: Detectar la anomalía."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.history: Dict[str, List[TelemetrySnapshot]] = {}

    def ingest(self, snapshot: TelemetrySnapshot) -> None:
        key = f"{snapshot.node_id}:{snapshot.device_id or '_all'}"
        self.history.setdefault(key, []).append(snapshot)
        if len(self.history[key]) > self.config.history_window_min:
            self.history[key] = self.history[key][-self.config.history_window_min :]

    def detect(self, snapshot: TelemetrySnapshot, peers: Optional[List[TelemetrySnapshot]] = None) -> Optional[AnomalySignal]:
        self.ingest(snapshot)
        features: Dict[str, float] = {}
        contributors: List[str] = []
        thresholds = self.config.thresholds

        temp = snapshot.metrics.get("DCGM_FI_DEV_GPU_TEMP", 0.0)
        if temp > thresholds.gpu_temperature_c:
            features["temperature_z"] = (temp - thresholds.gpu_temperature_c) / max(1.0, thresholds.gpu_temperature_c)
            contributors.append(f"gpu_temp={temp:.1f}C")

        vram_used = snapshot.metrics.get("DCGM_FI_DEV_FB_USED", 0.0)
        vram_total = snapshot.metrics.get("DCGM_FI_DEV_FB_TOTAL", 1.0)
        vram_pct = vram_used / vram_total * 100
        if vram_pct > thresholds.gpu_vram_used_pct:
            features["vram_pressure"] = vram_pct
            contributors.append(f"vram_used_pct={vram_pct:.1f}%")

        xid = snapshot.metrics.get("DCGM_FI_DEV_XID_ERRORS", 0.0)
        if xid > 0:
            features["memory_xid"] = xid
            contributors.append(f"xid_errors={int(xid)}")

        pcie = snapshot.metrics.get("DCGM_FI_DEV_PCIE_REPLAY", 0.0)
        if pcie > 200.0:
            features["pcie_replay"] = pcie
            contributors.append(f"pcie_replay={pcie:.1f}")

        pkt_loss = snapshot.metrics.get("node_network_transmit_drop_total", 0.0)
        if pkt_loss > thresholds.network_packet_loss_pct:
            features["network_loss"] = pkt_loss
            contributors.append(f"network_drop={pkt_loss:.1f}")

        util = snapshot.metrics.get("DCGM_FI_DEV_GPU_UTIL", 0.0)
        if util < thresholds.gpu_util_low_pct:
            features["gpu_util_low"] = thresholds.gpu_util_low_pct - util
            contributors.append(f"gpu_util_low={util:.1f}%")

        # Análisis de deriva temporal
        key = f"{snapshot.node_id}:{snapshot.device_id or '_all'}"
        hist = self.history.get(key, [])
        if len(hist) >= 5:
            temps = [s.metrics.get("DCGM_FI_DEV_GPU_TEMP", 0.0) for s in hist]
            try:
                mean_temp = statistics.mean(temps)
                stdev_temp = statistics.stdev(temps) or 1.0
                z_temp = (temp - mean_temp) / stdev_temp
                if abs(z_temp) > 2.0:
                    features["temperature_drift_z"] = z_temp
                    contributors.append(f"temperature_drift_z={z_temp:.2f}")
            except statistics.StatisticsError:
                pass

        # Comparación con homólogos
        if peers:
            peer_temps = [p.metrics.get("DCGM_FI_DEV_GPU_TEMP", 0.0) for p in peers]
            if peer_temps:
                peer_mean = sum(peer_temps) / len(peer_temps)
                if temp > peer_mean * 1.15:
                    features["peer_temp_deviation"] = (temp - peer_mean) / max(1.0, peer_mean)
                    contributors.append(f"peer_temp_deviation={features['peer_temp_deviation']:.2f}")

        if not features:
            return None

        score = min(1.0, sum(abs(v) for v in features.values()) / max(1.0, len(features) * 0.5))
        if score < thresholds.anomaly_score:
            return None

        return AnomalySignal(
            node_id=snapshot.node_id,
            score=round(score, 4),
            features=features,
            contributing_metrics=contributors,
            timestamp=snapshot.timestamp,
            confidence=round(min(1.0, score + 0.05), 4),
        )

    def classify_severity(self, signal: AnomalySignal) -> str:
        score = signal.score
        contributors = set(signal.contributing_metrics)
        if score >= 0.95 or any("xid" in c for c in contributors):
            return SeverityLevel.S3
        if score >= 0.85:
            return SeverityLevel.S2
        if score >= 0.75:
            return SeverityLevel.S1
        return SeverityLevel.S0
