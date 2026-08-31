import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from lockean_lite.market_evidence import (
    MarketBar,
    MarketEvidence,
)

from lockean_lite.market_entry_policy import (
    MarketEntryEvaluation,
    breakout_filter_passes,
    bullish_trend_filter_passes,
    evaluate_market_entry_policy,
    momentum_filter_passes,
    volatility_filter_passes,
)

def _market_evidence_from_closes(
    evidence_id,
    closes,
    symbol="SPY",
):
    start = datetime(
        2026,
        1,
        1,
        21,
        0,
        tzinfo=timezone.utc,
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

    return MarketEvidence(
        evidence_id=evidence_id,
        symbol=symbol,
        as_of=bars[-1].timestamp,
        source="alpaca",
        bars=bars,
    )

def _market_evidence_from_highs_and_closes(
    evidence_id,
    highs,
    closes,
):
    start = datetime(
        2026,
        1,
        1,
        21,
        0,
        tzinfo=timezone.utc,
    )

    bars = tuple(
        MarketBar(
            timestamp=start + timedelta(days=index),
            open=close,
            high=high,
            low=close,
            close=close,
            volume=1_000_000,
        )
        for index, (high, close) in enumerate(
            zip(highs, closes)
        )
    )

    return MarketEvidence(
        evidence_id=evidence_id,
        symbol="SPY",
        as_of=bars[-1].timestamp,
        source="alpaca",
        bars=bars,
    )


@pytest.mark.parametrize(
    ("evidence_id", "highs", "closes", "expected"),
    [
        (
            "breakout-insufficient",
            [Decimal("110")] * 19 + [Decimal("112")],
            [Decimal("100")] * 19 + [Decimal("111")],
            False,
        ),
        (
            "breakout-not-confirmed",
            [Decimal("110")] * 20 + [Decimal("112")],
            [Decimal("100")] * 20 + [Decimal("110")],
            False,
        ),
        (
            "breakout-confirmed",
            [Decimal("110")] * 20 + [Decimal("112")],
            [Decimal("100")] * 20 + [Decimal("111")],
            True,
        ),
    ],
)
def test_breakout_filter_requires_close_above_previous_20_session_high(
    evidence_id,
    highs,
    closes,
    expected,
):
    evidence = _market_evidence_from_highs_and_closes(
        evidence_id,
        highs,
        closes,
    )

    assert breakout_filter_passes(evidence) is expected


@pytest.mark.parametrize(
    ("evidence_id", "closes", "expected"),
    [
        (
            "vix-insufficient",
            [Decimal("20")] * 19,
            False,
        ),
        (
            "vix-not-below-average",
            [Decimal("20")] * 20,
            False,
        ),
        (
            "vix-below-average",
            [Decimal("20")] * 19 + [Decimal("10")],
            True,
        ),
    ],
)
def test_volatility_filter_requires_vix_below_20_day_average(
    evidence_id,
    closes,
    expected,
):
    evidence = _market_evidence_from_closes(
        evidence_id,
        closes,
        symbol="VIX",
    )

    assert volatility_filter_passes(evidence) is expected


@pytest.mark.parametrize(
    ("evidence_id", "closes", "expected"),
    [
        (
            "evidence-rsi-insufficient",
            [Decimal("100")] * 14,
            False,
        ),
        (
            "evidence-rsi-low",
            [
                Decimal("100"),
                Decimal("101"),
                Decimal("99"),
                Decimal("100"),
                Decimal("98"),
                Decimal("99"),
                Decimal("97"),
                Decimal("98"),
                Decimal("96"),
                Decimal("97"),
                Decimal("95"),
                Decimal("96"),
                Decimal("94"),
                Decimal("95"),
                Decimal("93"),
            ],
            False,
        ),
        (
            "evidence-rsi-valid",
            [
                Decimal("100"),
                Decimal("103"),
                Decimal("101"),
                Decimal("104"),
                Decimal("102"),
                Decimal("105"),
                Decimal("103"),
                Decimal("106"),
                Decimal("104"),
                Decimal("107"),
                Decimal("105"),
                Decimal("108"),
                Decimal("106"),
                Decimal("109"),
                Decimal("107"),
            ],
            True,
        ),
        (
            "evidence-rsi-overbought",
            [
                Decimal("100"),
                Decimal("103"),
                Decimal("102"),
                Decimal("105"),
                Decimal("104"),
                Decimal("107"),
                Decimal("106"),
                Decimal("109"),
                Decimal("108"),
                Decimal("111"),
                Decimal("110"),
                Decimal("113"),
                Decimal("112"),
                Decimal("115"),
                Decimal("114"),
            ],
            False,
        ),
    ],
)
def test_momentum_filter_enforces_rsi14_range(
    evidence_id,
    closes,
    expected,
):
    evidence = _market_evidence_from_closes(
        evidence_id,
        closes,
    )

    assert momentum_filter_passes(evidence) is expected


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

@pytest.mark.parametrize(
    (
        "trend_passes",
        "momentum_passes",
        "breakout_passes",
        "volatility_passes",
        "expected",
    ),
    [
        (
            False,
            True,
            True,
            True,
            MarketEntryEvaluation(
                passed=False,
                reason="trend_filter_failed",
            ),
        ),
        (
            True,
            False,
            True,
            True,
            MarketEntryEvaluation(
                passed=False,
                reason="momentum_filter_failed",
            ),
        ),
        (
            True,
            True,
            False,
            True,
            MarketEntryEvaluation(
                passed=False,
                reason="breakout_filter_failed",
            ),
        ),
        (
            True,
            True,
            True,
            False,
            MarketEntryEvaluation(
                passed=False,
                reason="volatility_filter_failed",
            ),
        ),
        (
            True,
            True,
            True,
            True,
            MarketEntryEvaluation(
                passed=True,
                reason="entry_conditions_satisfied",
            ),
        ),
    ],
)
def test_market_entry_policy_returns_exact_deterministic_reason(
    monkeypatch,
    trend_passes,
    momentum_passes,
    breakout_passes,
    volatility_passes,
    expected,
):
    spy_evidence = object()
    vix_evidence = object()

    monkeypatch.setattr(
        "lockean_lite.market_entry_policy.bullish_trend_filter_passes",
        lambda evidence: trend_passes,
    )

    monkeypatch.setattr(
        "lockean_lite.market_entry_policy.momentum_filter_passes",
        lambda evidence: momentum_passes,
    )

    monkeypatch.setattr(
        "lockean_lite.market_entry_policy.breakout_filter_passes",
        lambda evidence: breakout_passes,
    )

    monkeypatch.setattr(
        "lockean_lite.market_entry_policy.volatility_filter_passes",
        lambda evidence: volatility_passes,
    )

    result = evaluate_market_entry_policy(
        spy_evidence=spy_evidence,
        vix_evidence=vix_evidence,
    )

    assert result == expected