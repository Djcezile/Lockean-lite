from datetime import date, datetime, timezone
from decimal import Decimal

from lockean_lite.entry_portfolio_policy import (
    evaluate_entry_proposal_policy,
)
from lockean_lite.option_leg import OptionLeg
from lockean_lite.option_quote_snapshot import OptionQuoteSnapshot
from lockean_lite.paper_portfolio_snapshot import (
    PaperPortfolioSnapshot,
    PaperPositionSnapshot,
    PendingMlegOrderSnapshot,
)
from lockean_lite.trade_proposal import TradeProposal


EXPIRATION = date(2026, 9, 18)
NOW = datetime(2026, 9, 10, 14, 0, tzinfo=timezone.utc)


def _quote(symbol, strike):
    return OptionQuoteSnapshot(
        contract_symbol=symbol,
        underlying_symbol="SPY",
        option_type="call",
        strike=Decimal(str(strike)),
        expiration=EXPIRATION,
        bid_price=Decimal("1.00"),
        ask_price=Decimal("1.05"),
        quote_timestamp=NOW,
        source="alpaca",
    )


def _position(symbol, qty, cost_basis):
    return PaperPositionSnapshot(
        symbol=symbol,
        asset_class="option",
        qty=Decimal(str(qty)),
        market_value=Decimal("0"),
        cost_basis=Decimal(str(cost_basis)),
        current_price=Decimal("0"),
        unrealized_pl=Decimal("0"),
        unrealized_plpc=Decimal("0"),
    )


def _snapshot(*, positions=(), pending_orders=()):
    units = sum(abs(position.qty) for position in positions)
    return PaperPortfolioSnapshot(
        status="ACTIVE",
        currency="USD",
        trading_blocked=False,
        cash=Decimal("100000"),
        equity=Decimal("100000"),
        last_equity=Decimal("100000"),
        buying_power=Decimal("400000"),
        options_buying_power=Decimal("100000"),
        portfolio_value=Decimal("100000"),
        starting_equity=Decimal("100000"),
        total_pl=Decimal("0"),
        day_pl=Decimal("0"),
        unrealized_pl=Decimal("0"),
        positions=tuple(positions),
        option_contract_units=units,
        managed_spreads=int(units / Decimal("2")),
        pending_mleg_orders=tuple(pending_orders),
    )


def _proposal(*, buy_strike=762, sell_strike=764):
    return TradeProposal(
        proposal_id="proposal-1",
        symbol="SPY",
        strategy="defined_risk_option",
        contracts=1,
        legs=(
            OptionLeg(
                option_type="call",
                strike=Decimal(str(buy_strike)),
                expiration=EXPIRATION,
                side="buy",
            ),
            OptionLeg(
                option_type="call",
                strike=Decimal(str(sell_strike)),
                expiration=EXPIRATION,
                side="sell",
            ),
        ),
        net_debit=Decimal("0.50"),
    )


def _quotes():
    return (
        _quote("SPY260918C00762000", 762),
        _quote("SPY260918C00763000", 763),
        _quote("SPY260918C00764000", 764),
        _quote("SPY260918C00765000", 765),
    )


def test_rejects_third_unit_of_same_exact_vertical():
    snapshot = _snapshot(
        positions=(
            _position("SPY260918C00762000", 2, "200"),
            _position("SPY260918C00764000", -2, "-100"),
        )
    )

    decision = evaluate_entry_proposal_policy(
        proposal=_proposal(),
        candidate_quotes=_quotes(),
        snapshot=snapshot,
        maximum_same_structure_units=2,
    )

    assert not decision.allowed
    assert decision.reason == "same_structure_concentration_limit_reached"


def test_allows_different_vertical_when_structure_cap_is_not_reached():
    snapshot = _snapshot(
        positions=(
            _position("SPY260918C00762000", 2, "200"),
            _position("SPY260918C00764000", -2, "-100"),
        )
    )

    decision = evaluate_entry_proposal_policy(
        proposal=_proposal(buy_strike=763, sell_strike=765),
        candidate_quotes=_quotes(),
        snapshot=snapshot,
        maximum_same_structure_units=2,
    )

    assert decision.allowed
    assert decision.reason == "entry_portfolio_policy_passed"


def test_rejects_entry_that_overlaps_a_pending_exit_contract():
    pending = PendingMlegOrderSnapshot(
        order_id="exit-1",
        remaining_units=1,
        purpose="exit",
        submitted_at=NOW,
        symbols=(
            "SPY260918C00762000",
            "SPY260918C00764000",
        ),
    )

    decision = evaluate_entry_proposal_policy(
        proposal=_proposal(),
        candidate_quotes=_quotes(),
        snapshot=_snapshot(pending_orders=(pending,)),
    )

    assert not decision.allowed
    assert decision.reason == "entry_conflicts_with_pending_exit_order"


def test_rejects_buy_to_open_against_existing_short_contract():
    decision = evaluate_entry_proposal_policy(
        proposal=_proposal(),
        candidate_quotes=_quotes(),
        snapshot=_snapshot(
            positions=(
                _position("SPY260918C00762000", -1, "-50"),
            )
        ),
    )

    assert not decision.allowed
    assert decision.reason == "buy_to_open_conflicts_with_short_position"


def test_rejects_sell_to_open_against_existing_long_contract():
    decision = evaluate_entry_proposal_policy(
        proposal=_proposal(),
        candidate_quotes=_quotes(),
        snapshot=_snapshot(
            positions=(
                _position("SPY260918C00764000", 1, "50"),
            )
        ),
    )

    assert not decision.allowed
    assert decision.reason == "sell_to_open_conflicts_with_long_position"
