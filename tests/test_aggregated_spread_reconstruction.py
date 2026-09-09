from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

from lockean_lite.paper_portfolio_snapshot import (
    PaperPortfolioSnapshot,
    PaperPositionSnapshot,
    PendingMlegOrderSnapshot,
)
from lockean_lite.position_exit_manager import (
    identify_managed_bull_call_spreads,
    run_paper_spread_exit_cycle,
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


def _snapshot(*, pending_orders=()):
    positions = (
        _position(
            "SPY260918C00766000",
            4,
            "400",
        ),
        _position(
            "SPY260918C00767000",
            -3,
            "-150",
        ),
        _position(
            "SPY260918C00768000",
            -1,
            "-20",
        ),
    )

    pending_units = sum(
        order.remaining_units
        for order in pending_orders
    )

    return PaperPortfolioSnapshot(
        status="ACTIVE",
        currency="USD",
        trading_blocked=False,
        cash=Decimal("99900"),
        equity=Decimal("100000"),
        last_equity=Decimal("100000"),
        buying_power=Decimal("399000"),
        options_buying_power=Decimal("99900"),
        portfolio_value=Decimal("100000"),
        starting_equity=Decimal("100000"),
        total_pl=Decimal("0"),
        day_pl=Decimal("0"),
        unrealized_pl=Decimal("0"),
        positions=positions,
        option_contract_units=Decimal("8"),
        managed_spreads=4,
        pending_spread_units=pending_units,
        pending_exit_spread_units=pending_units,
        pending_mleg_orders=pending_orders,
    )


class MappedOptionDataClient:
    def get_option_latest_quote(self, request):
        quotes = {
            "SPY260918C00766000": SimpleNamespace(
                bid_price=Decimal("0.90"),
                ask_price=Decimal("0.95"),
            ),
            "SPY260918C00767000": SimpleNamespace(
                bid_price=Decimal("0.15"),
                ask_price=Decimal("0.20"),
            ),
            "SPY260918C00768000": SimpleNamespace(
                bid_price=Decimal("0.01"),
                ask_price=Decimal("0.05"),
            ),
        }
        return {
            symbol: quotes[symbol]
            for symbol in request.symbol_or_symbols
        }


class FakeTradingClient:
    def __init__(self):
        self.orders = []

    def submit_order(self, *, order_data):
        self.orders.append(order_data)
        return SimpleNamespace(id="aggregate-exit-1")


def test_reconstructs_aggregated_long_inventory_into_two_verticals():
    spreads = identify_managed_bull_call_spreads(
        _snapshot()
    )

    assert len(spreads) == 2
    assert [spread.contracts for spread in spreads] == [3, 1]
    assert [spread.long_symbol for spread in spreads] == [
        "SPY260918C00766000",
        "SPY260918C00766000",
    ]
    assert [spread.short_symbol for spread in spreads] == [
        "SPY260918C00767000",
        "SPY260918C00768000",
    ]
    assert spreads[0].entry_debit_per_contract == Decimal("0.5")
    assert spreads[1].entry_debit_per_contract == Decimal("0.8")


def test_exit_cycle_can_close_one_reconstructed_aggregated_vertical():
    trading_client = FakeTradingClient()

    result = run_paper_spread_exit_cycle(
        trading_client=trading_client,
        option_data_client=MappedOptionDataClient(),
        snapshot=_snapshot(),
        take_profit_percent=Decimal("10"),
        stop_loss_percent=Decimal("50"),
    )

    assert result.submitted
    assert result.reason == "take_profit_exit_submitted"
    assert result.expected_return_percent == Decimal("40.00")
    assert result.broker_order_id == "aggregate-exit-1"
    assert len(trading_client.orders) == 1
    assert trading_client.orders[0].qty == 3


def test_pending_exit_on_one_pair_does_not_hide_other_pair_sharing_long_leg():
    now = datetime(2026, 9, 10, 15, 0, tzinfo=timezone.utc)
    pending_exit = PendingMlegOrderSnapshot(
        order_id="exit-766-767",
        remaining_units=3,
        purpose="exit",
        submitted_at=now - timedelta(minutes=1),
        symbols=(
            "SPY260918C00766000",
            "SPY260918C00767000",
        ),
    )
    trading_client = FakeTradingClient()

    result = run_paper_spread_exit_cycle(
        trading_client=trading_client,
        option_data_client=MappedOptionDataClient(),
        snapshot=_snapshot(
            pending_orders=(pending_exit,)
        ),
        take_profit_percent=Decimal("5"),
        stop_loss_percent=Decimal("50"),
        now_fn=lambda: now,
    )

    assert result.submitted
    assert result.reason == "take_profit_exit_submitted"
    assert len(trading_client.orders) == 1
    order = trading_client.orders[0]
    assert order.qty == 1
    assert order.legs[0].symbol == "SPY260918C00766000"
    assert order.legs[1].symbol == "SPY260918C00768000"
