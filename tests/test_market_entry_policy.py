from datetime import datetime, timedelta, timezone
from decimal import Decimal

from lockean_lite.market_evidence import (
    MarketBar,
    MarketEvidence,
)
from lockean_lite.market_entry_policy import (
    bullish_trend_filter_passes,
)


def test_bullish_trend_filter_passes_when_close_is_above_sma50_and_sma50_is_above_sma200():
    start = datetime(
        2026,
        1,
        1,
        21,
        0,
        tzinfo=timezone.utc,
    )

    closes = (
        [Decimal("100")] * 150
        + [Decimal("120")] * 49
        + [Decimal("130")]
    )

    bars = tuple(
        MarketBar(
            timestamp=start + timedelta(days=index),
            open=close,
            high=close,
            low=close,
            close=close,
            volume=1_000_000,
        )
        for index, close in enumerate(closes)
    )

    evidence = MarketEvidence(
        evidence_id="evidence-002",
        symbol="SPY",
        as_of=bars[-1].timestamp,
        source="alpaca",
        bars=bars,
    )

    assert bullish_trend_filter_passes(evidence) is True

def test_bullish_trend_filter_fails_closed_with_fewer_than_200_bars():
    start = datetime(
        2026,
        1,
        1,
        21,
        0,
        tzinfo=timezone.utc,
    )

    closes = (
        [Decimal("100")] * 19
        + [Decimal("130")]
    )

    bars = tuple(
        MarketBar(
            timestamp=start + timedelta(days=index),
            open=close,
            high=close,
            low=close,
            close=close,
            volume=1_000_000,
        )
        for index, close in enumerate(closes)
    )

    evidence = MarketEvidence(
        evidence_id="evidence-003",
        symbol="SPY",
        as_of=bars[-1].timestamp,
        source="alpaca",
        bars=bars,
    )

    assert bullish_trend_filter_passes(evidence) is False

def test_bullish_trend_filter_fails_when_latest_close_is_not_above_sma50():
    start = datetime(
        2026,
        1,
        1,
        21,
        0,
        tzinfo=timezone.utc,
    )

    closes = (
        [Decimal("100")] * 150
        + [Decimal("120")] * 49
        + [Decimal("110")]
    )

    bars = tuple(
        MarketBar(
            timestamp=start + timedelta(days=index),
            open=close,
            high=close,
            low=close,
            close=close,
            volume=1_000_000,
        )
        for index, close in enumerate(closes)
    )

    evidence = MarketEvidence(
        evidence_id="evidence-004",
        symbol="SPY",
        as_of=bars[-1].timestamp,
        source="alpaca",
        bars=bars,
    )

    assert bullish_trend_filter_passes(evidence) is False


def test_bullish_trend_filter_fails_when_sma50_is_not_above_sma200():
    start = datetime(
        2026,
        1,
        1,
        21,
        0,
        tzinfo=timezone.utc,
    )

    closes = (
        [Decimal("120")] * 150
        + [Decimal("100")] * 49
        + [Decimal("110")]
    )

    bars = tuple(
        MarketBar(
            timestamp=start + timedelta(days=index),
            open=close,
            high=close,
            low=close,
            close=close,
            volume=1_000_000,
        )
        for index, close in enumerate(closes)
    )

    evidence = MarketEvidence(
        evidence_id="evidence-005",
        symbol="SPY",
        as_of=bars[-1].timestamp,
        source="alpaca",
        bars=bars,
    )

    assert bullish_trend_filter_passes(evidence) is False