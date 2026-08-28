"""Detección de anomalías para UC-273.

Implementa:
- SpoofingDetector: detecta spoofing/layering, quote stuffing, anomalías de precio.
- CollusionDetector: detecta colusión, wash trading, sincronización sospechosa.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional

from config import AnomalyConfig, get_config


@dataclass
class QuoteEvent:
    """Evento de quote/orden."""
    agent_id: str
    symbol: str
    side: Literal["bid", "ask"]
    price: float
    quantity: float
    timestamp: float
    is_cancelled: bool = False
    cancel_latency_ms: float = 0.0


class SpoofingDetector:
    """Detecta spoofing/layering, quote stuffing y anomalías de precio."""

    def __init__(self, config: AnomalyConfig | None = None) -> None:
        cfg = config or get_config().anomaly
        self.cancel_ratio_threshold = cfg.cancel_ratio_threshold
        self.fast_cancel_ms = cfg.fast_cancel_ms
        self.z_score_threshold = cfg.z_score_threshold
        self._quotes: Dict[str, deque] = defaultdict(lambda: deque(maxlen=cfg.spoofing_window_size))
        self._market_prices: Dict[str, deque] = defaultdict(lambda: deque(maxlen=500))

    def record_quote(self, quote: QuoteEvent) -> Optional[Dict[str, Any]]:
        """Registra quote y retorna alerta si detecta anomalía."""
        self._quotes[quote.agent_id].append(quote)
        if not quote.is_cancelled:
            self._market_prices[quote.symbol].append(quote.price)

        alerts = []
        for detect_fn in (self._detect_high_cancel_ratio, self._detect_fast_cancels):
            alert = detect_fn(quote.agent_id)
            if alert:
                alerts.append(alert)

        price_alert = self._detect_price_anomaly(quote)
        if price_alert:
            alerts.append(price_alert)

        stuffing = self._detect_quote_stuffing(quote.agent_id)
        if stuffing:
            alerts.append(stuffing)

        if alerts:
            return {
                "agent_id": quote.agent_id,
                "alerts": alerts,
                "severity": max(a["severity"] for a in alerts),
            }
        return None

    def _detect_high_cancel_ratio(self, agent_id: str) -> Optional[dict]:
        quotes = list(self._quotes[agent_id])
        if len(quotes) < 20:
            return None
        cancelled = sum(1 for q in quotes if q.is_cancelled)
        ratio = cancelled / len(quotes)
        if ratio > self.cancel_ratio_threshold:
            return {"type": "high_cancel_ratio", "ratio": round(ratio, 3), "severity": min(1.0, (ratio - 0.5) * 2)}
        return None

    def _detect_fast_cancels(self, agent_id: str) -> Optional[dict]:
        quotes = list(self._quotes[agent_id])
        fast = [q for q in quotes if q.is_cancelled and q.cancel_latency_ms < self.fast_cancel_ms]
        if len(fast) >= 5:
            avg_qty = sum(q.quantity for q in fast) / len(fast)
            if avg_qty > 100:
                return {"type": "layering_suspected", "fast_cancels": len(fast), "avg_quantity": round(avg_qty, 1), "severity": 0.8}
        return None

    def _detect_price_anomaly(self, quote: QuoteEvent) -> Optional[dict]:
        prices = list(self._market_prices.get(quote.symbol, []))
        if len(prices) < 30:
            return None
        mean = sum(prices) / len(prices)
        variance = sum((p - mean) ** 2 for p in prices) / len(prices)
        std = variance ** 0.5
        if std == 0:
            return None
        z_score = abs(quote.price - mean) / std
        if z_score > self.z_score_threshold:
            return {"type": "price_anomaly", "z_score": round(z_score, 2), "severity": min(1.0, z_score / 5.0)}
        return None

    def _detect_quote_stuffing(self, agent_id: str) -> Optional[dict]:
        quotes = list(self._quotes[agent_id])
        if len(quotes) < 50:
            return None
        recent = quotes[-50:]
        time_span = recent[-1].timestamp - recent[0].timestamp
        if time_span <= 0:
            return None
        rate = len(recent) / time_span
        if rate > 100:
            return {"type": "quote_stuffing", "rate_per_second": round(rate, 1), "severity": min(1.0, rate / 500)}
        return None


class CollusionDetector:
    """Detecta colusión, wash trading y sincronización sospechosa."""

    def __init__(self, config: AnomalyConfig | None = None) -> None:
        cfg = config or get_config().anomaly
        self.correlation_threshold = cfg.collusion_correlation
        self.min_observations = cfg.collusion_min_observations
        self._action_series: Dict[str, List] = defaultdict(list)

    def record_action(self, agent_id: str, action_type: str, price: float, timestamp: float) -> None:
        self._action_series[agent_id].append((timestamp, action_type, price))
        if len(self._action_series[agent_id]) > 1000:
            self._action_series[agent_id] = self._action_series[agent_id][-1000:]

    def detect_collusion(self) -> List[dict]:
        alerts = []
        agents = list(self._action_series.keys())
        for i, a1 in enumerate(agents):
            for a2 in agents[i + 1:]:
                alert = self._check_pair_correlation(a1, a2)
                if alert:
                    alerts.append(alert)
        alerts.extend(self._detect_wash_trading())
        alerts.extend(self._detect_synchronization())
        return alerts

    def _check_pair_correlation(self, a1: str, a2: str) -> Optional[dict]:
        s1 = self._action_series[a1]
        s2 = self._action_series[a2]
        if len(s1) < self.min_observations or len(s2) < self.min_observations:
            return None
        prices1 = [p for _, _, p in s1[-200:]]
        prices2 = [p for _, _, p in s2[-200:]]
        min_len = min(len(prices1), len(prices2))
        if min_len < 20:
            return None
        p1 = prices1[-min_len:]
        p2 = prices2[-min_len:]
        corr = self._pearson(p1, p2)
        if corr is not None and abs(corr) > self.correlation_threshold:
            return {"type": "collusion_suspected", "agents": [a1, a2], "correlation": round(corr, 4), "severity": min(1.0, (abs(corr) - 0.7) * 3.3)}
        return None

    def _detect_wash_trading(self) -> List[dict]:
        alerts = []
        for agent_id, actions in self._action_series.items():
            buys = [(t, p) for t, a, p in actions if a == "buy"]
            sells = [(t, p) for t, a, p in actions if a == "sell"]
            wash_count = 0
            for bt, bp in buys:
                for st, sp in sells:
                    if abs(st - bt) < 5.0 and bp > 0 and abs(sp - bp) / bp < 0.001:
                        wash_count += 1
            if wash_count >= 3:
                alerts.append({"type": "wash_trading", "agent": agent_id, "wash_count": wash_count, "severity": min(1.0, wash_count / 10)})
        return alerts

    def _detect_synchronization(self) -> List[dict]:
        alerts = []
        windows: Dict[int, List[str]] = defaultdict(list)
        for agent_id, actions in self._action_series.items():
            for t, _, _ in actions[-100:]:
                windows[int(t)].append(agent_id)
        for window, agents in windows.items():
            unique = set(agents)
            if len(unique) >= 4 and len(agents) >= 10:
                alerts.append({"type": "synchronized_action", "window": window, "agents": list(unique), "severity": 0.6})
        return alerts

    @staticmethod
    def _pearson(x: List[float], y: List[float]) -> Optional[float]:
        n = len(x)
        if n < 2:
            return None
        mx = sum(x) / n
        my = sum(y) / n
        num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
        dx = sum((xi - mx) ** 2 for xi in x) ** 0.5
        dy = sum((yi - my) ** 2 for yi in y) ** 0.5
        if dx == 0 or dy == 0:
            return None
        return num / (dx * dy)
