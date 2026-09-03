from decimal import Decimal
from types import SimpleNamespace

from lockean_lite.agent_market_context import (
    build_agent_market_context,
)


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
        "spy_close": "765.13",
        "trend": "PASS",
        "momentum": "PASS",
        "breakout": "FAIL",
        "vix_close": "15.200000",
        "volatility": "FAIL",
    }