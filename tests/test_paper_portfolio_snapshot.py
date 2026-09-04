from decimal import Decimal
from types import SimpleNamespace

from lockean_lite.paper_portfolio_snapshot import (
    create_paper_portfolio_snapshot,
    render_paper_portfolio_snapshot,
)


def _account(**overrides):
    values = {
        "status": SimpleNamespace(value="ACTIVE"),
        "currency": "USD",
        "trading_blocked": False,
        "cash": "99800.00",
        "equity": "100125.50",
        "last_equity": "100050.00",
        "buying_power": "199600.00",
        "options_buying_power": "99750.00",
        "portfolio_value": "100125.50",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _position(
    symbol,
    qty,
    unrealized_pl,
    *,
    asset_class="us_option",
):
    return SimpleNamespace(
        symbol=symbol,
        asset_class=SimpleNamespace(
            value=asset_class
        ),
        qty=str(qty),
        market_value="100.00",
        cost_basis="90.00",
        current_price="1.00",
        unrealized_pl=str(unrealized_pl),
        unrealized_plpc="0.10",
    )


def test_portfolio_snapshot_uses_live_account_values_for_pnl():
    snapshot = create_paper_portfolio_snapshot(
        account=_account(),
        positions=[],
        starting_equity=Decimal("100000.00"),
    )

    assert snapshot.equity == Decimal("100125.50")
    assert snapshot.total_pl == Decimal("125.50")
    assert snapshot.day_pl == Decimal("75.50")
    assert snapshot.options_buying_power == Decimal("99750.00")


def test_portfolio_snapshot_counts_spread_units_from_option_contract_quantity():
    snapshot = create_paper_portfolio_snapshot(
        account=_account(),
        positions=(
            _position("SPY-CALL-A", 3, "15.00"),
            _position("SPY-CALL-B", -3, "-5.00"),
        ),
    )

    assert snapshot.option_contract_units == Decimal("6")
    assert snapshot.managed_spreads == 3
    assert snapshot.unrealized_pl == Decimal("10.00")


def test_portfolio_snapshot_conservatively_counts_odd_option_leg_quantity():
    snapshot = create_paper_portfolio_snapshot(
        account=_account(),
        positions=(
            _position("SPY-CALL-A", 1, "0"),
        ),
    )

    assert snapshot.managed_spreads == 1


def test_rendered_portfolio_telemetry_surfaces_alpaca_equity_and_pnl():
    snapshot = create_paper_portfolio_snapshot(
        account=_account(),
        positions=[],
    )

    output = render_paper_portfolio_snapshot(snapshot)

    assert "CURRENT EQUITY:  $100,125.50" in output
    assert "TOTAL P&L:       $125.50" in output
    assert "DAY P&L:         $75.50" in output
