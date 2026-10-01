from datetime import date, datetime, timezone
from decimal import Decimal

from lockean_lite.ai_recommendation_provider import (
    StructuredAIRecommendationProvider,
    build_recommendation_prompt,
)
from lockean_lite.option_quote_snapshot import OptionQuoteSnapshot


def _candidate(strike, bid, ask):
    strike_decimal = Decimal(str(strike))
    return OptionQuoteSnapshot(
        contract_symbol=(
            "SPY261002C"
            f"{int(strike_decimal * 1000):08d}"
        ),
        underlying_symbol="SPY",
        option_type="call",
        strike=strike_decimal,
        expiration=date(2026, 10, 2),
        bid_price=Decimal(str(bid)),
        ask_price=Decimal(str(ask)),
        quote_timestamp=datetime(
            2026,
            10,
            1,
            14,
            30,
            tzinfo=timezone.utc,
        ),
        source="alpaca",
    )


def _candidates():
    return (
        _candidate(670, "2.40", "2.45"),
        _candidate(672, "1.80", "1.85"),
    )


def test_profit_first_prompt_optimizes_net_profit_without_activity_bias():
    prompt = build_recommendation_prompt(
        proposal_id="profit-first-001",
        candidate_quotes=_candidates(),
        maximum_allowed_loss=Decimal("150.00"),
        market_context={
            "trend": "PASS",
            "momentum": "PASS",
            "breakout": "PASS",
            "volatility": "PASS",
            "intraday_status": "AVAILABLE",
            "spy_session_direction": "UP",
            "intraday_direction_15m": "UP",
            "intraday_direction_30m": "UP",
        },
        activity_mode="profit_first",
    )

    assert "PROFIT-FIRST PAPER MODE" in prompt
    assert "positive net realized P&L" in prompt
    assert "Never trade to generate activity" in prompt
    assert "NO_TRADE is the preferred decision" in prompt
    assert "transaction costs" in prompt
    assert "bull call debit spread" in prompt
    assert "Prefer decision=TRADE" not in prompt

    assert "broker instructions" in prompt
    assert "authorization_receipt" not in prompt


def test_profit_first_provider_passes_mode_without_gaining_authority():
    captured = {}

    def fake_model(prompt):
        captured["prompt"] = prompt
        return """
        {
          "decision": "NO_TRADE",
          "symbol": null,
          "expiration": null,
          "buy_strike": null,
          "sell_strike": null,
          "contracts": null,
          "option_type": null,
          "rationale": "No sufficiently clear net edge after execution friction."
        }
        """

    provider = StructuredAIRecommendationProvider(
        proposal_id_provider=lambda: "profit-first-002",
        model_callable=fake_model,
        maximum_allowed_loss=Decimal("150.00"),
        activity_mode="profit_first",
    )

    result = provider(
        _candidates(),
        market_context={"trend": "FAIL"},
    )

    assert result is None
    assert provider.last_decision == "NO_TRADE"
    assert "PROFIT-FIRST PAPER MODE" in captured["prompt"]

