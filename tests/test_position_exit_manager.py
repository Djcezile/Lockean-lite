from decimal import Decimal
from types import SimpleNamespace

from alpaca.trading.enums import (
    OrderClass,
    OrderSide,
    PositionIntent,
)

from lockean_lite.paper_portfolio_snapshot import (
    PaperPortfolioSnapshot,
    PaperPositionSnapshot,
)
from lockean_lite.position_exit_manager import (
    identify_managed_bull_call_spreads,
    run_paper_spread_exit_cycle,
)


def _position(
    *,
    symbol,
    qty,
    market_value,
    cost_basis,
    unrealized_pl,
):
    return PaperPositionSnapshot(
        symbol=symbol,
        asset_class="option",
        qty=Decimal(str(qty)),
        market_value=Decimal(str(market_value)),
        cost_basis=Decimal(str(cost_basis)),
        current_price=Decimal("1.00"),
        unrealized_pl=Decimal(str(unrealized_pl)),
        unrealized_plpc=Decimal("0"),
    )


def _snapshot(*, pending=0):
    positions = (
        _position(
            symbol="SPY260918C00782000",
            qty=1,
            market_value="120",
            cost_basis="100",
            unrealized_pl="20",
        ),
        _position(
            symbol="SPY260918C00785000",
            qty=-1,
            market_value="-45",
            cost_basis="-40",
            unrealized_pl="-5",
        ),
    )

    return PaperPortfolioSnapshot(
        status="ACTIVE",
        currency="USD",
        trading_blocked=False,
        cash=Decimal("99940"),
        equity=Decimal("100015"),
        last_equity=Decimal("100000"),
        buying_power=Decimal("399000"),
        options_buying_power=Decimal("99940"),
        portfolio_value=Decimal("100015"),
        starting_equity=Decimal("100000"),
        total_pl=Decimal("15"),
        day_pl=Decimal("15"),
        unrealized_pl=Decimal("15"),
        positions=positions,
        option_contract_units=Decimal("2"),
        managed_spreads=1,
        pending_spread_units=pending,
    )


class FakeOptionDataClient:
    def __init__(self, *, long_bid, short_ask):
        self.long_bid = long_bid
        self.short_ask = short_ask

    def get_option_latest_quote(self, request):
        return {
            "SPY260918C00782000": SimpleNamespace(
                bid_price=self.long_bid,
                ask_price=Decimal("9.99"),
            ),
            "SPY260918C00785000": SimpleNamespace(
                bid_price=Decimal("0.01"),
                ask_price=self.short_ask,
            ),
        }


class FakeTradingClient:
    def __init__(self):
        self.orders = []

    def submit_order(self, *, order_data):
        self.orders.append(order_data)
        return SimpleNamespace(id="exit-order-001")


def test_identifies_existing_bull_call_as_one_managed_spread():
    spreads = identify_managed_bull_call_spreads(
        _snapshot()
    )

    assert len(spreads) == 1

    spread = spreads[0]

    assert spread.long_symbol == (
        "SPY260918C00782000"
    )
    assert spread.short_symbol == (
        "SPY260918C00785000"
    )
    assert spread.contracts == 1
    assert spread.entry_debit_per_contract == Decimal(
        "0.6"
    )


def test_take_profit_submits_single_mleg_close_for_existing_spread():
    trading_client = FakeTradingClient()

    result = run_paper_spread_exit_cycle(
        trading_client=trading_client,
        option_data_client=FakeOptionDataClient(
            long_bid=Decimal("1.20"),
            short_ask=Decimal("0.45"),
        ),
        snapshot=_snapshot(),
        take_profit_percent=Decimal("10"),
        stop_loss_percent=Decimal("50"),
    )

    assert result.submitted
    assert result.reason == (
        "take_profit_exit_submitted"
    )
    assert result.broker_order_id == (
        "exit-order-001"
    )
    assert result.expected_return_percent == Decimal(
        "25.00"
    )

    assert len(trading_client.orders) == 1

    order = trading_client.orders[0]

    assert order.order_class == OrderClass.MLEG
    assert order.qty == 1
    assert order.limit_price == -0.75

    long_leg, short_leg = order.legs

    assert long_leg.side == OrderSide.SELL
    assert long_leg.position_intent == (
        PositionIntent.SELL_TO_CLOSE
    )

    assert short_leg.side == OrderSide.BUY
    assert short_leg.position_intent == (
        PositionIntent.BUY_TO_CLOSE
    )


def test_stop_loss_submits_risk_reducing_close_before_new_entry():
    result = run_paper_spread_exit_cycle(
        trading_client=FakeTradingClient(),
        option_data_client=FakeOptionDataClient(
            long_bid=Decimal("0.40"),
            short_ask=Decimal("0.10"),
        ),
        snapshot=_snapshot(),
        take_profit_percent=Decimal("10"),
        stop_loss_percent=Decimal("40"),
    )

    assert result.submitted
    assert result.reason == (
        "stop_loss_exit_submitted"
    )
    assert result.expected_return_percent == Decimal(
        "-50.00"
    )


def test_no_exit_when_executable_return_is_inside_thresholds():
    trading_client = FakeTradingClient()

    result = run_paper_spread_exit_cycle(
        trading_client=trading_client,
        option_data_client=FakeOptionDataClient(
            long_bid=Decimal("0.90"),
            short_ask=Decimal("0.30"),
        ),
        snapshot=_snapshot(),
        take_profit_percent=Decimal("10"),
        stop_loss_percent=Decimal("50"),
    )

    assert not result.submitted
    assert result.reason == (
        "no_managed_spread_exit_trigger"
    )
    assert trading_client.orders == []


def test_pending_mleg_blocks_duplicate_exit_and_new_entry():
    trading_client = FakeTradingClient()

    result = run_paper_spread_exit_cycle(
        trading_client=trading_client,
        option_data_client=FakeOptionDataClient(
            long_bid=Decimal("1.20"),
            short_ask=Decimal("0.45"),
        ),
        snapshot=_snapshot(pending=1),
    )

    assert not result.submitted
    assert result.block_new_entries
    assert result.reason == (
        "pending_mleg_order_exists"
    )
    assert trading_client.orders == []
