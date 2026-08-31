from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from lockean_lite.ai_recommendation_provider import (
    StructuredAIRecommendationProvider,
    build_recommendation_prompt,
)
from lockean_lite.option_quote_snapshot import (
    OptionQuoteSnapshot,
)


QUOTE_TIME = datetime(
    2026,
    8,
    28,
    19,
    59,
    59,
    tzinfo=timezone.utc,
)


def _quote(
    *,
    strike,
    bid,
    ask,
):
    strike_decimal = Decimal(str(strike))

    return OptionQuoteSnapshot(
        contract_symbol=(
            f"SPY260918C"
            f"{int(strike_decimal * 1000):08d}"
        ),
        underlying_symbol="SPY",
        option_type="call",
        strike=strike_decimal,
        expiration=date(2026, 9, 18),
        bid_price=Decimal(str(bid)),
        ask_price=Decimal(str(ask)),
        quote_timestamp=QUOTE_TIME,
        source="alpaca",
    )


def _candidates():
    return (
        _quote(
            strike=782,
            bid="2.96",
            ask="3.03",
        ),
        _quote(
            strike=783,
            bid="2.68",
            ask="2.72",
        ),
        _quote(
            strike=787,
            bid="1.75",
            ask="1.76",
        ),
    )


def test_ai_prompt_contains_candidate_market_context_but_no_authorization_power():
    prompt = build_recommendation_prompt(
        proposal_id="proposal-ai-live-001",
        candidate_quotes=_candidates(),
    )

    assert "782" in prompt
    assert "787" in prompt
    assert "2.96" in prompt
    assert "3.03" in prompt

    assert "net_debit" not in prompt
    assert "maximum_loss" not in prompt
    assert "authorization_receipt" not in prompt


def test_structured_ai_provider_returns_only_spread_recommendation():
    raw_response = """
    {
      "symbol": "SPY",
      "expiration": "2026-09-18",
      "buy_strike": "782",
      "sell_strike": "787",
      "contracts": 1
    }
    """

    provider = StructuredAIRecommendationProvider(
        proposal_id_provider=lambda: (
            "proposal-ai-live-002"
        ),
        model_callable=lambda prompt: raw_response,
    )

    recommendation = provider(
        _candidates()
    )

    assert recommendation.proposal_id == (
        "proposal-ai-live-002"
    )

    assert recommendation.symbol == "SPY"
    assert recommendation.expiration == date(
        2026,
        9,
        18,
    )

    assert recommendation.buy_strike == Decimal(
        "782"
    )

    assert recommendation.sell_strike == Decimal(
        "787"
    )

    assert recommendation.contracts == 1

    assert not hasattr(
        recommendation,
        "net_debit",
    )


def test_ai_provider_rejects_invalid_json():
    provider = StructuredAIRecommendationProvider(
        proposal_id_provider=lambda: (
            "proposal-ai-live-003"
        ),
        model_callable=lambda prompt: (
            "I recommend buying 782 and selling 787."
        ),
    )

    with pytest.raises(
        ValueError,
        match="ai_recommendation_invalid_json",
    ):
        provider(
            _candidates()
        )


def test_ai_provider_rejects_extra_financial_authority_fields():
    raw_response = """
    {
      "symbol": "SPY",
      "expiration": "2026-09-18",
      "buy_strike": "782",
      "sell_strike": "787",
      "contracts": 1,
      "net_debit": "0.25"
    }
    """

    provider = StructuredAIRecommendationProvider(
        proposal_id_provider=lambda: (
            "proposal-ai-live-004"
        ),
        model_callable=lambda prompt: raw_response,
    )

    with pytest.raises(
        ValueError,
        match="ai_recommendation_schema_invalid",
    ):
        provider(
            _candidates()
        )


def test_ai_provider_rejects_missing_required_fields():
    raw_response = """
    {
      "symbol": "SPY",
      "expiration": "2026-09-18",
      "buy_strike": "782",
      "contracts": 1
    }
    """

    provider = StructuredAIRecommendationProvider(
        proposal_id_provider=lambda: (
            "proposal-ai-live-005"
        ),
        model_callable=lambda prompt: raw_response,
    )

    with pytest.raises(
        ValueError,
        match="ai_recommendation_schema_invalid",
    ):
        provider(
            _candidates()
        )

def test_ai_prompt_receives_maximum_loss_policy_as_context_only():
    prompt = build_recommendation_prompt(
        proposal_id="proposal-ai-policy-001",
        candidate_quotes=_candidates(),
        maximum_allowed_loss=Decimal("150.00"),
    )

    assert (
        "maximum_allowed_loss_usd=150.00"
        in prompt
    )

    # Policy knowledge does not expand AI output authority.
    assert "net_debit" not in prompt
    assert "authorization_receipt" not in prompt


def test_structured_ai_provider_passes_policy_context_to_model():
    captured = {}

    raw_response = """
    {
      "symbol": "SPY",
      "expiration": "2026-09-18",
      "buy_strike": "782",
      "sell_strike": "787",
      "contracts": 1
    }
    """

    def fake_model(prompt):
        captured["prompt"] = prompt
        return raw_response

    provider = StructuredAIRecommendationProvider(
        proposal_id_provider=lambda: (
            "proposal-ai-policy-002"
        ),
        model_callable=fake_model,
        maximum_allowed_loss=Decimal("150.00"),
    )

    recommendation = provider(
        _candidates()
    )

    assert (
        "maximum_allowed_loss_usd=150.00"
        in captured["prompt"]
    )

    assert recommendation.buy_strike == Decimal(
        "782"
    )

    assert recommendation.sell_strike == Decimal(
        "787"
    )

    assert not hasattr(
        recommendation,
        "maximum_loss",
    )