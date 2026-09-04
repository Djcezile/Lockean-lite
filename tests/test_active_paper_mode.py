from datetime import date, datetime, timezone
from decimal import Decimal

from lockean_lite.ai_recommendation_provider import (
    StructuredAIRecommendationProvider,
    build_recommendation_prompt,
)
from lockean_lite.option_quote_snapshot import (
    OptionQuoteSnapshot,
)


def _candidate(strike, bid, ask):
    return OptionQuoteSnapshot(
        contract_symbol=(
            "SPY260918C"
            f"{int(Decimal(str(strike)) * 1000):08d}"
        ),
        underlying_symbol="SPY",
        option_type="call",
        strike=Decimal(str(strike)),
        expiration=date(2026, 9, 18),
        bid_price=Decimal(str(bid)),
        ask_price=Decimal(str(ask)),
        quote_timestamp=datetime(
            2026,
            9,
            4,
            14,
            30,
            tzinfo=timezone.utc,
        ),
        source="alpaca",
    )


def _candidates():
    return (
        _candidate(782, "2.50", "2.55"),
        _candidate(783, "2.10", "2.15"),
        _candidate(785, "1.50", "1.55"),
    )


def test_active_paper_prompt_prefers_bounded_activity_without_granting_authority():
    prompt = build_recommendation_prompt(
        proposal_id="active-paper-001",
        candidate_quotes=_candidates(),
        maximum_allowed_loss=Decimal("150.00"),
        market_context={
            "trend": "PASS",
            "momentum": "PASS",
            "breakout": "FAIL",
            "volatility": "PASS",
        },
        activity_mode="active_paper",
    )

    assert "ACTIVE PAPER MODE" in prompt
    assert "Prefer decision=TRADE" in prompt
    assert "single FAIL does not" in prompt
    assert "maximum_allowed_loss_usd=150.00" in prompt

    assert "broker instructions" in prompt
    assert "authorization_receipt" not in prompt


def test_active_paper_provider_passes_activity_mode_to_model_prompt():
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
          "contracts": null
        }
        """

    provider = StructuredAIRecommendationProvider(
        proposal_id_provider=lambda: "active-paper-002",
        model_callable=fake_model,
        maximum_allowed_loss=Decimal("150.00"),
        activity_mode="active_paper",
    )

    result = provider(
        _candidates(),
        market_context={
            "trend": "PASS",
            "momentum": "PASS",
            "breakout": "FAIL",
            "volatility": "PASS",
        },
    )

    assert result is None
    assert "ACTIVE PAPER MODE" in captured["prompt"]
