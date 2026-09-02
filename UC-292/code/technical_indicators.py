"""Indicadores técnicos reutilizables para UC-292."""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd


def _to_series(prices, index=None) -> pd.Series:
    if isinstance(prices, pd.Series):
        return prices
    return pd.Series(prices, index=index, dtype=float)


def sma(series: pd.Series | List[float] | np.ndarray, window: int) -> pd.Series:
    """Media móvil simple."""
    s = _to_series(series)
    return s.rolling(window=window, min_periods=1).mean()


def ema(series: pd.Series | List[float] | np.ndarray, span: int) -> pd.Series:
    """Media móvil exponencial."""
    s = _to_series(series)
    return s.ewm(span=span, adjust=False, min_periods=1).mean()


def rsi(series: pd.Series | List[float] | np.ndarray, window: int = 14) -> pd.Series:
    """Relative Strength Index."""
    s = _to_series(series)
    delta = s.diff()
    gain = delta.where(delta > 0, 0.0).rolling(window=window, min_periods=1).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=window, min_periods=1).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi_vals = 100.0 - (100.0 / (1.0 + rs))
    return rsi_vals.fillna(50.0)


def macd(
    series: pd.Series | List[float] | np.ndarray,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> Dict[str, pd.Series]:
    """MACD, señal e histograma."""
    s = _to_series(series)
    ema_fast = ema(s, fast)
    ema_slow = ema(s, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return {"macd": macd_line, "signal": signal_line, "histogram": histogram}


def bollinger_position(series: pd.Series | List[float] | np.ndarray, window: int = 20) -> pd.Series:
    """Posición relativa dentro de las bandas de Bollinger."""
    s = _to_series(series)
    ma = sma(s, window)
    std = s.rolling(window=window, min_periods=1).std().replace(0, np.nan)
    upper = ma + 2 * std
    lower = ma - 2 * std
    position = (s - lower) / (upper - lower)
    return position.fillna(0.5)


def atr_from_prices(
    close: pd.Series | List[float] | np.ndarray,
    window: int = 14,
) -> pd.Series:
    """ATR simplificado usando solo cierres (aproximación para ticks sin high/low)."""
    c = _to_series(close)
    tr = c.diff().abs().fillna(0.0)
    return tr.rolling(window=window, min_periods=1).mean()


def obv(close: pd.Series | List[float], volume: pd.Series | List[float]) -> pd.Series:
    """On-Balance Volume."""
    c = _to_series(close)
    v = _to_series(volume)
    change = c.diff()
    direction = pd.Series(np.where(change > 0, 1, np.where(change < 0, -1, 0)), index=c.index)
    obv_vals = (direction * v).cumsum()
    return obv_vals


def returns(series: pd.Series | List[float] | np.ndarray) -> pd.Series:
    s = _to_series(series)
    return s.pct_change(fill_method=None).fillna(0.0)


def volatility(series: pd.Series | List[float] | np.ndarray, window: int = 20) -> pd.Series:
    """Volatilidad de retornos."""
    r = returns(series)
    return r.rolling(window=window, min_periods=1).std().fillna(0.0)


def extract_features(
    prices: List[float] | pd.Series,
    volume: Optional[List[float] | pd.Series] = None,
    cfg=None,
) -> Dict[str, float]:
    """Extrae el último valor de cada indicador configurado."""
    from config import get_config

    cfg = cfg or get_config().features
    s = _to_series(prices)
    vol = _to_series(volume) if volume is not None else pd.Series([0.0] * len(s), index=s.index)

    sma_fast = sma(s, cfg.sma_fast)
    sma_slow = sma(s, cfg.sma_slow)
    rsi_vals = rsi(s, cfg.rsi_window)
    macd_vals = macd(s, cfg.macd_fast, cfg.macd_slow, cfg.macd_signal)
    bb_pos = bollinger_position(s, cfg.bollinger_window)
    atr_vals = atr_from_prices(s, cfg.atr_window)
    obv_vals = obv(s, vol)
    vol_vals = volatility(s, cfg.sma_fast)

    trend_direction = 1 if sma_fast.iloc[-1] > sma_slow.iloc[-1] else -1
    volume_trend = 1 if len(obv_vals) > 5 and obv_vals.iloc[-1] > obv_vals.iloc[-5] else -1

    return {
        "sma_fast": float(sma_fast.iloc[-1]),
        "sma_slow": float(sma_slow.iloc[-1]),
        "rsi": float(rsi_vals.iloc[-1]),
        "macd": float(macd_vals["macd"].iloc[-1]),
        "macd_signal": float(macd_vals["signal"].iloc[-1]),
        "atr": float(atr_vals.iloc[-1]),
        "bollinger_position": float(bb_pos.iloc[-1]),
        "obv": float(obv_vals.iloc[-1]),
        "volume_trend": int(volume_trend),
        "trend_direction": int(trend_direction),
        "volatility": float(vol_vals.iloc[-1]),
        "latest_price": float(s.iloc[-1]),
    }


def classify_regime(features: Dict[str, float]) -> str:
    """Clasificación simple de régimen de mercado."""
    rsi = features.get("rsi", 50.0)
    trend = features.get("trend_direction", 0)
    vol = features.get("volatility", 0.0)
    bb = features.get("bollinger_position", 0.5)

    if trend > 0 and vol < 0.015:
        return "trending_bullish_low_vol"
    if trend > 0:
        return "trending_bullish"
    if trend < 0 and vol < 0.015:
        return "trending_bearish_low_vol"
    if trend < 0:
        return "trending_bearish"
    if bb > 0.8 or bb < 0.2:
        return "mean_reverting_extreme"
    return "lateral"
