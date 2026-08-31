from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from lockean_lite.option_leg import OptionLeg
from lockean_lite.option_quote_snapshot import (
    OptionQuoteSnapshot,
)
from lockean_lite.proposal_pricing import (
    build_quote_priced_trade_proposal,
    derive_bull_call_spread_limit_debit,
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


def _buy_leg():
    return OptionLeg(
        option_type="call",
        strike=Decimal("782"),
        expiration=date(2026, 9, 18),
        side="buy",
    )


def _sell_leg():
    return OptionLeg(
        option_type="call",
        strike=Decimal("787"),
        expiration=date(2026, 9, 18),
        side="sell",
    )


def _buy_quote():
    return OptionQuoteSnapshot(
        contract_symbol="SPY260918C00782000",
        underlying_symbol="SPY",
        option_type="call",
        strike=Decimal("782"),
        expiration=date(2026, 9, 18),
        bid_price=Decimal("2.96"),
        ask_price=Decimal("3.03"),
        quote_timestamp=QUOTE_TIME,
        source="alpaca",
    )


def _sell_quote():
    return OptionQuoteSnapshot(
        contract_symbol="SPY260918C00787000",
        underlying_symbol="SPY",
        option_type="call",
        strike=Decimal("787"),
        expiration=date(2026, 9, 18),
        bid_price=Decimal("1.75"),
        ask_price=Decimal("1.76"),
        quote_timestamp=QUOTE_TIME,
        source="alpaca",
    )


def test_lockean_derives_spread_debit_from_buy_ask_minus_sell_bid():
    debit = derive_bull_call_spread_limit_debit(
        symbol="SPY",
        buy_leg=_buy_leg(),
        sell_leg=_sell_leg(),
        buy_quote=_buy_quote(),
        sell_quote=_sell_quote(),
    )

    assert debit == Decimal("1.28")


def test_spread_pricing_rejects_quote_that_does_not_match_selected_leg():
    wrong_buy_quote = OptionQuoteSnapshot(
        contract_symbol="SPY260918C00783000",
        underlying_symbol="SPY",
        option_type="call",
        strike=Decimal("783"),
        expiration=date(2026, 9, 18),
        bid_price=Decimal("2.68"),
        ask_price=Decimal("2.72"),
        quote_timestamp=QUOTE_TIME,
        source="alpaca",
    )

    with pytest.raises(
        ValueError,
        match="option_quote_leg_mismatch",
    ):
        derive_bull_call_spread_limit_debit(
            symbol="SPY",
            buy_leg=_buy_leg(),
            sell_leg=_sell_leg(),
            buy_quote=wrong_buy_quote,
            sell_quote=_sell_quote(),
        )


def test_spread_pricing_fails_closed_on_non_positive_derived_debit():
    crossed_sell_quote = OptionQuoteSnapshot(
        contract_symbol="SPY260918C00787000",
        underlying_symbol="SPY",
        option_type="call",
        strike=Decimal("787"),
        expiration=date(2026, 9, 18),
        bid_price=Decimal("3.50"),
        ask_price=Decimal("3.60"),
        quote_timestamp=QUOTE_TIME,
        source="alpaca",
    )

    with pytest.raises(
        ValueError,
        match="invalid_derived_net_debit",
    ):
        derive_bull_call_spread_limit_debit(
            symbol="SPY",
            buy_leg=_buy_leg(),
            sell_leg=_sell_leg(),
            buy_quote=_buy_quote(),
            sell_quote=crossed_sell_quote,
        )


def test_quote_priced_proposal_preserves_ai_selected_structure_but_lockean_sets_debit():
    proposal = build_quote_priced_trade_proposal(
        proposal_id="proposal-real-candidate-001",
        symbol="SPY",
        contracts=1,
        buy_leg=_buy_leg(),
        sell_leg=_sell_leg(),
        buy_quote=_buy_quote(),
        sell_quote=_sell_quote(),
    )

    assert proposal.proposal_id == (
        "proposal-real-candidate-001"
    )

    assert proposal.symbol == "SPY"
    assert proposal.contracts == 1
    assert proposal.legs == (
        _buy_leg(),
        _sell_leg(),
    )

    assert proposal.net_debit == Decimal("1.28")