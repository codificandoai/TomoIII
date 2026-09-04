"""Pipeline de percepción del mercado para UC-292.

Convierte datos brutos (ticks, noticias) en un modelo del mundo estructurado
sobre el que los agentes de trading pueden razonar.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from scipy import stats

from config import AppConfig, FeatureConfig, MarketConfig, get_config
from models import MarketSnapshot, MarketTick, NewsItem, ProcessedNews, TechnicalSnapshot
from technical_indicators import classify_regime, extract_features


class NewsPipeline:
    """Preprocesa titulares de mercado con NLP ligero."""

    _POSITIVE = {
        "up", "rise", "rising", "gain", "gains", "bullish", "strong", "growth",
        "beat", "beats", "surge", "surges", "rally", "rallies", "rocket", "soar",
        "outperform", "upgrade", "buy", "moon", "mooning",
    }
    _NEGATIVE = {
        "down", "fall", "falling", "drop", "drops", "bearish", "weak", "weakness",
        "loss", "losses", "miss", "misses", "crash", "crashes", "sell", "selling",
        "underperform", "downgrade", "fraud", "lawsuit", "recession",
    }
    _STOPWORDS = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "must", "shall", "can", "need", "dare",
        "ought", "used", "to", "of", "in", "for", "on", "with", "at", "by",
        "from", "as", "into", "through", "during", "before", "after", "above",
        "below", "between", "among", "and", "or", "but", "so", "yet", "if",
        "because", "although", "though", "while", "where", "when", "that",
        "which", "who", "whom", "whose", "what", "this", "these", "those",
    }
    _CREDIBILITY = {
        "bloomberg": 0.95,
        "reuters": 0.95,
        "wsj": 0.92,
        "ft": 0.92,
        "cnbc": 0.75,
        "marketwatch": 0.70,
        "twitter": 0.45,
        "reddit": 0.35,
        "unknown": 0.50,
    }

    def tokenize(self, text: str) -> List[str]:
        words = re.findall(r"[a-zA-Z]{2,}", text.lower())
        return [w for w in words if w not in self._STOPWORDS]

    def extract_entities(self, tokens: List[str]) -> List[str]:
        """Detecta entidades como tickers en mayúsculas."""
        entities: List[str] = []
        for tok in tokens:
            if tok.isupper() and 1 <= len(tok) <= 5:
                entities.append(tok)
        return list(dict.fromkeys(entities))

    def score_source(self, source: str) -> float:
        return self._CREDIBILITY.get(source.lower(), 0.50)

    def sentiment_score(self, tokens: List[str]) -> float:
        pos = sum(1 for t in tokens if t in self._POSITIVE)
        neg = sum(1 for t in tokens if t in self._NEGATIVE)
        total = pos + neg
        if total == 0:
            return 0.0
        return (pos - neg) / total

    def impact_lookup(self, entities: List[str]) -> float:
        """Impacto histórico estimado por entidad (mock lookup)."""
        return 0.0

    def preprocess(self, item: NewsItem) -> ProcessedNews:
        tokens = self.tokenize(item.text)
        raw_words = re.findall(r"[A-Za-z]{2,}", item.text)
        entities = self.extract_entities(raw_words)
        sentiment = self.sentiment_score(tokens)
        credibility = self.score_source(item.source)

        latency = 0.0
        if item.published_at and item.received_at:
            try:
                pub = self._parse_iso(item.published_at)
                rec = self._parse_iso(item.received_at)
                latency = max(0.0, (rec - pub).total_seconds())
            except Exception:
                latency = 0.0

        return ProcessedNews(
            text=item.text,
            tokens=tokens,
            entities=entities,
            source_credibility=credibility,
            latency_seconds=latency,
            sentiment=sentiment,
            market_impact_historical=self.impact_lookup(entities),
        )

    @staticmethod
    def _parse_iso(value: str) -> datetime:
        v = value.replace("Z", "+00:00")
        return datetime.fromisoformat(v)


class MarketPerceptionPipeline:
    """Construye la percepción estructurada del entorno de trading."""

    def __init__(
        self,
        market_cfg: Optional[MarketConfig] = None,
        feature_cfg: Optional[FeatureConfig] = None,
        news_pipeline: Optional[NewsPipeline] = None,
    ) -> None:
        self.market_cfg = market_cfg or get_config().market
        self.feature_cfg = feature_cfg or get_config().features
        self.news_pipeline = news_pipeline or NewsPipeline()

    def preprocess_market_data(self, raw_ticks: pd.DataFrame) -> pd.DataFrame:
        """Limpia y normaliza datos de mercado."""
        if raw_ticks.empty:
            return raw_ticks

        df = raw_ticks.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index("timestamp").sort_index()

        # Descartar outliers de transmisión si hay suficientes muestras
        if len(df) >= 10 and "last_price" in df.columns:
            z = np.abs(stats.zscore(df["last_price"], nan_policy="omit"))
            df = df[z < self.market_cfg.outlier_z]

        # Rellenar gaps cortos con ffill + interpolate solo en columnas numéricas
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        df_num = df[numeric_cols].resample(f"{self.market_cfg.resample_interval_ms}ms").ffill().interpolate(method="linear")
        for col in df.columns:
            if col not in numeric_cols and col in df.columns:
                df_num[col] = df[col].resample(f"{self.market_cfg.resample_interval_ms}ms").ffill()
        return df_num

    def preprocess_news(self, raw_headlines: List[NewsItem]) -> List[ProcessedNews]:
        return [self.news_pipeline.preprocess(item) for item in raw_headlines]

    def build_snapshot(
        self,
        symbol: str,
        ticks: List[MarketTick],
        processed_news: Optional[List[ProcessedNews]] = None,
    ) -> MarketSnapshot:
        """Genera una instantánea estructurada del mercado."""
        if not ticks:
            return MarketSnapshot(
                symbol=symbol,
                timestamp=now_iso(),
                latest_price=0.0,
                features=TechnicalSnapshot(symbol=symbol, timestamp=now_iso()),
                regime="no_data",
            )

        rows = [t.model_dump() for t in sorted(ticks, key=lambda x: x.timestamp)]
        df = pd.DataFrame(rows)
        if "last_price" not in df.columns:
            raise ValueError("MarketTicks deben incluir last_price")

        latest_price = float(df["last_price"].iloc[-1])
        latest_ts = str(df["timestamp"].iloc[-1])

        clean_df = self.preprocess_market_data(df)
        prices = clean_df["last_price"].tolist()
        volumes = clean_df["volume"].tolist() if "volume" in clean_df else [0.0] * len(prices)

        feature_values = extract_features(prices, volumes, self.feature_cfg)
        features = TechnicalSnapshot(symbol=symbol, timestamp=latest_ts, **feature_values)
        regime = classify_regime(feature_values)

        sentiment = 0.0
        credibility = 0.5
        if processed_news:
            total_weight = 0.0
            weighted_sentiment = 0.0
            cred_sum = 0.0
            for news in processed_news:
                weight = max(0.0, 1.0 - news.latency_seconds / 300.0) * news.source_credibility
                weighted_sentiment += news.sentiment * weight
                total_weight += weight
                cred_sum += news.source_credibility
            if total_weight > 0:
                sentiment = weighted_sentiment / total_weight
            if processed_news:
                credibility = cred_sum / len(processed_news)

        return MarketSnapshot(
            symbol=symbol,
            timestamp=latest_ts,
            latest_price=latest_price,
            features=features,
            news_sentiment=sentiment,
            news_credibility=credibility,
            regime=regime,
        )

    def perceive(
        self,
        request_id: str,
        ticks_by_symbol: Dict[str, List[MarketTick]],
        news: List[NewsItem],
    ) -> Dict[str, MarketSnapshot]:
        """Percibe el entorno completo: ticks + noticias -> snapshots por símbolo."""
        processed_news = self.preprocess_news(news)
        snapshots: Dict[str, MarketSnapshot] = {}
        for symbol, ticks in ticks_by_symbol.items():
            snapshots[symbol] = self.build_snapshot(symbol, ticks, processed_news)
        return snapshots


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
