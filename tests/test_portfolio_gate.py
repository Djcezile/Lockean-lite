from decimal import Decimal
from types import SimpleNamespace

from lockean_lite.portfolio_gate import (
    evaluate_portfolio_entry,
)


def _snapshot(**overrides):
    values = {
        "status": "ACTIVE",
        "trading_blocked": False,
        "options_buying_power": Decimal("100000"),
        "day_pl": Decimal("0"),
        "managed_spreads": 0,
        "pending_spread_units": 0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_portfolio_gate_allows_entry_below_limits():
    result = evaluate_portfolio_entry(
        snapshot=_snapshot(managed_spreads=4),
        maximum_open_spreads=5,
        maximum_daily_loss=Decimal("750"),
    )

    assert result.allowed is True
    assert result.reason == "portfolio_entry_allowed"


def test_portfolio_gate_blocks_fifth_limit_from_becoming_sixth():
    result = evaluate_portfolio_entry(
        snapshot=_snapshot(managed_spreads=5),
        maximum_open_spreads=5,
    )

    assert result.allowed is False
    assert result.reason == "portfolio_spread_limit_reached"


def test_portfolio_gate_counts_pending_orders_against_five_spread_cap():
    result = evaluate_portfolio_entry(
        snapshot=_snapshot(
            managed_spreads=3,
            pending_spread_units=2,
        ),
        maximum_open_spreads=5,
    )

    assert result.allowed is False
    assert result.reason == "portfolio_spread_limit_reached"


def test_portfolio_gate_allows_when_filled_and_pending_total_is_below_cap():
    result = evaluate_portfolio_entry(
        snapshot=_snapshot(
            managed_spreads=2,
            pending_spread_units=2,
        ),
        maximum_open_spreads=5,
    )

    assert result.allowed is True
    assert result.reason == "portfolio_entry_allowed"


def test_portfolio_gate_blocks_after_daily_loss_limit():
    result = evaluate_portfolio_entry(
        snapshot=_snapshot(
            day_pl=Decimal("-750.00")
        ),
        maximum_daily_loss=Decimal("750.00"),
    )

    assert result.allowed is False
    assert result.reason == "daily_loss_limit_reached"


def test_portfolio_gate_blocks_when_options_buying_power_is_exhausted():
    result = evaluate_portfolio_entry(
        snapshot=_snapshot(
            options_buying_power=Decimal("0")
        )
    )

    assert result.allowed is False
    assert result.reason == "options_buying_power_exhausted"
