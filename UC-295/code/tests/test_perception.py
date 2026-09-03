"""Tests del pipeline de percepción."""
from __future__ import annotations

import datetime

from market_data import SyntheticMarketDataGenerator
from models import MarketTick, NewsItem
from perception import MarketPerceptionPipeline, NewsPipeline


def test_news_sentiment_positive():
    pipe = NewsPipeline()
    item = NewsItem(text="AAPL surges on strong earnings beat", source="bloomberg")
    processed = pipe.preprocess(item)
    assert processed.sentiment > 0
    assert processed.source_credibility > 0.9


def test_news_sentiment_negative():
    pipe = NewsPipeline()
    item = NewsItem(text="TSLA crashes after lawsuit", source="reddit")
    processed = pipe.preprocess(item)
    assert processed.sentiment < 0
    assert "TSLA" in processed.entities


def test_build_snapshot():
    gen = SyntheticMarketDataGenerator(seed=42)
    ticks = gen.generate_ticks("AAPL", n=100)
    pipe = MarketPerceptionPipeline()
    snapshot = pipe.build_snapshot("AAPL", ticks, [])
    assert snapshot.symbol == "AAPL"
    assert snapshot.latest_price > 0
    assert snapshot.features.rsi >= 0
    assert snapshot.regime in [
        "trending_bullish", "trending_bearish", "trending_bullish_low_vol",
        "trending_bearish_low_vol", "mean_reverting_extreme", "lateral",
    ]


def test_perceive_multiple_symbols():
    gen = SyntheticMarketDataGenerator(seed=42)
    ticks_aapl = gen.generate_ticks("AAPL", n=80)
    ticks_tsla = gen.generate_ticks("TSLA", n=80, start_price=200.0)
    pipe = MarketPerceptionPipeline()
    snapshots = pipe.perceive("req-1", {"AAPL": ticks_aapl, "TSLA": ticks_tsla}, [])
    assert set(snapshots.keys()) == {"AAPL", "TSLA"}
