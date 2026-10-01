from datetime import date
from decimal import Decimal

import pytest

from lockean_lite.option_leg import OptionLeg
from lockean_lite.profit_first_entry_policy import (
    evaluate_profit_first_entry,
)
from lockean_lite.trade_proposal import TradeProposal


EXPIRATION = date(2026, 10, 2)


def _proposal(
    *,
    option_type="call",
    buy_strike="670",
    sell_strike="672",
    net_debit="0.60",
):
    return TradeProposal(
        proposal_id="profit-policy-001",
        symbol="SPY",
        strategy="defined_risk_option",
        contracts=1,
        legs=(
            OptionLeg(
                option_type=option_type,
                strike=Decimal(buy_strike),
                expiration=EXPIRATION,
                side="buy",
            ),
            OptionLeg(
                option_type=option_type,
                strike=Decimal(sell_strike),
                expiration=EXPIRATION,
                side="sell",
            ),
        ),
        net_debit=(
            None
            if net_debit is None
            else Decimal(net_debit)
        ),
    )


def _context(**overrides):
    context = {
        "trend": "PASS",
        "momentum": "PASS",
        "breakout": "PASS",
        "volatility": "PASS",
        "intraday_status": "AVAILABLE",
        "spy_session_direction": "UP",
        "intraday_direction_15m": "UP",
        "intraday_direction_30m": "UP",
    }
    context.update(overrides)
    return context


def test_profit_first_policy_allows_high_confluence_positive_economics():
    result = evaluate_profit_first_entry(
        proposal=_proposal(),
        market_context=_context(),
    )

    assert result.allowed is True
    assert result.reason == "profit_first_entry_eligible"
    assert result.reward_to_risk > Decimal("1.50")


@pytest.mark.parametrize(
    ("signal", "expected_reason"),
    [
        ("trend", "profit_first_trend_not_confirmed"),
        ("momentum", "profit_first_momentum_not_confirmed"),
        ("breakout", "profit_first_breakout_not_confirmed"),
        ("volatility", "profit_first_volatility_not_confirmed"),
    ],
)
def test_profit_first_policy_requires_completed_session_confluence(
    signal,
    expected_reason,
):
    result = evaluate_profit_first_entry(
        proposal=_proposal(),
        market_context=_context(**{signal: "FAIL"}),
    )

    assert result.allowed is False
    assert result.reason == expected_reason


def test_profit_first_policy_waits_for_usable_intraday_evidence():
    result = evaluate_profit_first_entry(
        proposal=_proposal(),
        market_context=_context(intraday_status="WARMING_UP"),
    )

    assert result.allowed is False
    assert result.reason == "profit_first_intraday_not_ready"


@pytest.mark.parametrize(
    "overrides",
    [
        {"spy_session_direction": "DOWN"},
        {"intraday_direction_15m": "DOWN"},
        {"intraday_direction_30m": "FLAT"},
    ],
)
def test_profit_first_policy_requires_multi_horizon_upside_alignment(overrides):
    result = evaluate_profit_first_entry(
        proposal=_proposal(),
        market_context=_context(**overrides),
    )

    assert result.allowed is False
    assert result.reason == "profit_first_intraday_alignment_missing"


def test_profit_first_policy_rejects_unvalidated_bearish_strategy():
    result = evaluate_profit_first_entry(
        proposal=_proposal(
            option_type="put",
            buy_strike="672",
            sell_strike="670",
        ),
        market_context=_context(),
    )

    assert result.allowed is False
    assert result.reason == "profit_first_strategy_not_validated"


def test_profit_first_policy_rejects_weak_reward_to_risk_after_costs():
    result = evaluate_profit_first_entry(
        proposal=_proposal(
            buy_strike="670",
            sell_strike="671",
            net_debit="0.50",
        ),
        market_context=_context(),
    )

    assert result.allowed is False
    assert result.reason == "profit_first_reward_to_risk_below_minimum"
    assert result.reward_to_risk < Decimal("1.50")


def test_profit_first_policy_fails_closed_without_trusted_pricing():
    result = evaluate_profit_first_entry(
        proposal=_proposal(net_debit=None),
        market_context=_context(),
    )

    assert result.allowed is False
    assert result.reason == "profit_first_pricing_missing"

