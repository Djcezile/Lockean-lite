from dataclasses import FrozenInstanceError
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from lockean_lite.option_quote_snapshot import (
    OptionQuoteSnapshot,
)
from lockean_lite.trade_recommendation import (
    SpreadRecommendation,
    build_trade_proposal_from_recommendation,
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
    strike_code = int(strike * 1000)

    return OptionQuoteSnapshot(
        contract_symbol=(
            f"SPY260918C{strike_code:08d}"
        ),
        underlying_symbol="SPY",
        option_type="call",
        strike=Decimal(str(strike)),
        expiration=date(2026, 9, 18),
        bid_price=Decimal(str(bid)),
        ask_price=Decimal(str(ask)),
        quote_timestamp=QUOTE_TIME,
        source="alpaca",
    )


def _candidate_universe():
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


def test_ai_spread_recommendation_is_immutable_and_contains_no_price_authority():
    recommendation = SpreadRecommendation(
        proposal_id="proposal-ai-001",
        symbol="SPY",
        expiration=date(2026, 9, 18),
        buy_strike=Decimal("782"),
        sell_strike=Decimal("787"),
        contracts=1,
    )

    assert recommendation.buy_strike == Decimal("782")
    assert recommendation.sell_strike == Decimal("787")

    assert not hasattr(
        recommendation,
        "net_debit",
    )

    assert not hasattr(
        recommendation,
        "maximum_loss",
    )

    with pytest.raises(FrozenInstanceError):
        recommendation.contracts = 2


def test_lockean_builds_exact_quote_priced_proposal_from_recommendation():
    recommendation = SpreadRecommendation(
        proposal_id="proposal-ai-002",
        symbol="SPY",
        expiration=date(2026, 9, 18),
        buy_strike=Decimal("782"),
        sell_strike=Decimal("787"),
        contracts=1,
    )

    proposal = build_trade_proposal_from_recommendation(
        recommendation=recommendation,
        candidate_quotes=_candidate_universe(),
    )

    assert proposal.proposal_id == "proposal-ai-002"
    assert proposal.symbol == "SPY"
    assert proposal.contracts == 1

    assert proposal.legs[0].side == "buy"
    assert proposal.legs[0].strike == Decimal("782")

    assert proposal.legs[1].side == "sell"
    assert proposal.legs[1].strike == Decimal("787")

    assert proposal.net_debit == Decimal("1.28")


def test_recommendation_fails_closed_when_exact_candidate_is_missing():
    recommendation = SpreadRecommendation(
        proposal_id="proposal-ai-003",
        symbol="SPY",
        expiration=date(2026, 9, 18),
        buy_strike=Decimal("782"),
        sell_strike=Decimal("788"),
        contracts=1,
    )

    with pytest.raises(
        ValueError,
        match="recommended_option_quote_missing",
    ):
        build_trade_proposal_from_recommendation(
            recommendation=recommendation,
            candidate_quotes=_candidate_universe(),
        )


def test_recommendation_fails_closed_when_strike_order_is_invalid():
    recommendation = SpreadRecommendation(
        proposal_id="proposal-ai-004",
        symbol="SPY",
        expiration=date(2026, 9, 18),
        buy_strike=Decimal("787"),
        sell_strike=Decimal("782"),
        contracts=1,
    )

    with pytest.raises(
        ValueError,
        match="invalid_strike_order",
    ):
        build_trade_proposal_from_recommendation(
            recommendation=recommendation,
            candidate_quotes=_candidate_universe(),
        )


def test_recommendation_fails_closed_when_contract_quantity_is_invalid():
    recommendation = SpreadRecommendation(
        proposal_id="proposal-ai-005",
        symbol="SPY",
        expiration=date(2026, 9, 18),
        buy_strike=Decimal("782"),
        sell_strike=Decimal("787"),
        contracts=0,
    )

    with pytest.raises(
        ValueError,
        match="invalid_contract_quantity",
    ):
        build_trade_proposal_from_recommendation(
            recommendation=recommendation,
            candidate_quotes=_candidate_universe(),
        )