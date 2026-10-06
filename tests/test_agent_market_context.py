from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

from lockean_lite.agent_market_context import (
    build_agent_market_context,
)
from lockean_lite.market_evidence import MarketBar, MarketEvidence


def test_agent_market_context_uses_existing_market_signal_functions(
    monkeypatch,
):
    spy_evidence = SimpleNamespace(
        bars=(
            SimpleNamespace(
                close=Decimal("765.13"),
            ),
        ),
    )

    vix_evidence = SimpleNamespace(
        bars=(
            SimpleNamespace(
                close=Decimal("15.200000"),
            ),
        ),
    )

    monkeypatch.setattr(
        "lockean_lite.agent_market_context.bullish_trend_filter_passes",
        lambda evidence: True,
    )

    monkeypatch.setattr(
        "lockean_lite.agent_market_context.momentum_filter_passes",
        lambda evidence: True,
    )

    monkeypatch.setattr(
        "lockean_lite.agent_market_context.breakout_filter_passes",
        lambda evidence: False,
    )

    monkeypatch.setattr(
        "lockean_lite.agent_market_context.volatility_filter_passes",
        lambda evidence: False,
    )

    result = build_agent_market_context(
        spy_evidence=spy_evidence,
        vix_evidence=vix_evidence,
    )

    assert result == {
        "spy_completed_through": "UNKNOWN",
        "spy_close": "765.13",
        "spy_sma_50": "NA",
        "spy_sma_200": "NA",
        "spy_rsi_14": "NA",
        "spy_previous_20_session_high": "NA",
        "spy_breakout_distance_pct": "NA",
        "trend": "PASS",
        "momentum": "PASS",
        "breakout": "FAIL",
        "vix_completed_through": "UNKNOWN",
        "vix_close": "15.200000",
        "vix_sma_20": "NA",
        "vix_distance_from_sma_20_pct": "NA",
        "volatility": "FAIL",
    }


def _evidence(*, symbol, closes, highs=None):
    start = datetime(2026, 1, 1, 21, 0, tzinfo=timezone.utc)
    actual_highs = highs if highs is not None else closes
    bars = tuple(
        MarketBar(
            timestamp=start + timedelta(days=index),
            open=close,
            high=high,
            low=close,
            close=close,
            volume=1_000_000,
        )
        for index, (close, high) in enumerate(zip(closes, actual_highs))
    )
    return MarketEvidence(
        evidence_id=f"{symbol.lower()}-signal-basis",
        symbol=symbol,
        as_of=bars[-1].timestamp,
        source="test",
        bars=bars,
    )


def test_agent_market_context_records_numeric_basis_for_every_daily_gate():
    spy_closes = (
        [Decimal("100")] * 150
        + [Decimal("120")] * 49
        + [Decimal("130")]
    )
    spy_highs = [Decimal("120")] * 199 + [Decimal("132")]
    vix_closes = [Decimal("20")] * 19 + [Decimal("10")]

    result = build_agent_market_context(
        spy_evidence=_evidence(
            symbol="SPY",
            closes=spy_closes,
            highs=spy_highs,
        ),
        vix_evidence=_evidence(symbol="VIX", closes=vix_closes),
    )

    assert result["spy_completed_through"] == "2026-07-19"
    assert result["spy_close"] == "130"
    assert result["spy_sma_50"] == "120.200"
    assert result["spy_sma_200"] == "105.050"
    assert result["spy_rsi_14"] == "100.000"
    assert result["spy_previous_20_session_high"] == "120.000"
    assert result["spy_breakout_distance_pct"] == "8.333"
    assert result["trend"] == "PASS"
    assert result["momentum"] == "FAIL"
    assert result["breakout"] == "PASS"
    assert result["vix_completed_through"] == "2026-01-20"
    assert result["vix_close"] == "10"
    assert result["vix_sma_20"] == "19.500"
    assert result["vix_distance_from_sma_20_pct"] == "-48.718"
    assert result["volatility"] == "PASS"
