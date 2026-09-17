from decimal import Decimal
from types import SimpleNamespace

from lockean_lite.agent_market_context import build_agent_market_context
from lockean_lite.ai_recommendation_provider import build_recommendation_prompt
from lockean_lite.option_quote_snapshot import OptionQuoteSnapshot


def _spy_evidence(close="754.05"):
    return SimpleNamespace(
        bars=(SimpleNamespace(close=Decimal(close)),)
    )


def _vix_evidence(close="17.710000"):
    return SimpleNamespace(
        bars=(SimpleNamespace(close=Decimal(close)),)
    )


def test_agent_context_adds_session_return_vs_prior_close(monkeypatch):
    monkeypatch.setattr(
        "lockean_lite.agent_market_context.bullish_trend_filter_passes",
        lambda evidence: False,
    )
    monkeypatch.setattr(
        "lockean_lite.agent_market_context.momentum_filter_passes",
        lambda evidence: False,
    )
    monkeypatch.setattr(
        "lockean_lite.agent_market_context.breakout_filter_passes",
        lambda evidence: False,
    )
    monkeypatch.setattr(
        "lockean_lite.agent_market_context.volatility_filter_passes",
        lambda evidence: False,
    )

    context = build_agent_market_context(
        spy_evidence=_spy_evidence(),
        vix_evidence=_vix_evidence(),
        intraday_context={
            "intraday_status": "AVAILABLE",
            "intraday_spy_close": "761.12",
            "intraday_return_5m_pct": "-0.050",
            "intraday_direction_5m": "DOWN",
        },
    )

    assert context["spy_prior_close"] == "754.05"
    assert context["spy_session_return_pct"] == "0.938"
    assert context["spy_session_direction"] == "UP"
    assert context["intraday_return_5m_pct"] == "-0.050"
    assert context["intraday_direction_5m"] == "DOWN"


def test_session_scale_context_is_not_invented_without_intraday_price():
    context = build_agent_market_context(
        spy_evidence=_spy_evidence(),
        vix_evidence=_vix_evidence(),
        intraday_context={"intraday_status": "UNAVAILABLE"},
    )

    assert context["spy_prior_close"] == "754.05"
    assert "spy_session_return_pct" not in context
    assert "spy_session_direction" not in context


def test_balanced_prompt_weighs_session_scale_without_hard_veto():
    quote = OptionQuoteSnapshot(
        contract_symbol="SPY260918P00762000",
        underlying_symbol="SPY",
        option_type="put",
        strike=Decimal("762"),
        expiration=__import__("datetime").date(2026, 9, 18),
        bid_price=Decimal("1.00"),
        ask_price=Decimal("1.05"),
        quote_timestamp=__import__("datetime").datetime(
            2026, 9, 17, 14, 0,
            tzinfo=__import__("datetime").timezone.utc,
        ),
        source="alpaca",
    )

    prompt = build_recommendation_prompt(
        proposal_id="day9-session-scale",
        candidate_quotes=(quote,),
        market_context={
            "spy_prior_close": "754.05",
            "intraday_spy_close": "761.12",
            "spy_session_return_pct": "0.938",
            "spy_session_direction": "UP",
            "intraday_return_5m_pct": "-0.050",
            "intraday_direction_5m": "DOWN",
        },
        activity_mode="balanced",
    )

    assert "session-scale" in prompt.lower()
    assert "prior close" in prompt.lower()
    assert "small short-window" in prompt.lower()
    assert "does not automatically" in prompt.lower()
