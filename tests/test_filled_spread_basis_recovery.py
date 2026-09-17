from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from lockean_lite.filled_spread_basis import (
    read_open_spread_entry_basis,
)
from lockean_lite.paper_portfolio_snapshot import (
    PaperPortfolioSnapshot,
    PaperPositionSnapshot,
)
from lockean_lite.position_exit_manager import (
    identify_managed_debit_spreads,
    run_paper_spread_exit_cycle,
)


LONG = "SPY260918P00752000"
SHORT = "SPY260918P00751000"
STRUCTURE = frozenset({LONG, SHORT})


def _leg(symbol, intent):
    return SimpleNamespace(
        symbol=symbol,
        position_intent=intent,
    )


def _order(
    *,
    submitted_at,
    price,
    qty=1,
    purpose="entry",
    limit_price=None,
):
    if purpose == "entry":
        legs = (
            _leg(LONG, "buy_to_open"),
            _leg(SHORT, "sell_to_open"),
        )
    else:
        legs = (
            _leg(LONG, "sell_to_close"),
            _leg(SHORT, "buy_to_close"),
        )

    return SimpleNamespace(
        order_class="mleg",
        status="filled",
        qty=str(qty),
        filled_qty=str(qty),
        filled_avg_price=(
            None if price is None else str(price)
        ),
        limit_price=(
            None if limit_price is None else str(limit_price)
        ),
        submitted_at=submitted_at,
        legs=legs,
    )


class HistoryClient:
    def __init__(self, orders):
        self.orders = list(orders)
        self.filters = []

    def get_orders(self, *, filter):
        self.filters.append(filter)
        return list(self.orders)


class OptionClient:
    def get_option_latest_quote(self, request):
        return {
            LONG: SimpleNamespace(bid_price="0.40", ask_price="0.41"),
            SHORT: SimpleNamespace(bid_price="0.08", ask_price="0.09"),
        }


def _position(symbol, qty, cost_basis):
    return PaperPositionSnapshot(
        symbol=symbol,
        asset_class="us_option",
        qty=Decimal(str(qty)),
        market_value=Decimal("0"),
        cost_basis=Decimal(str(cost_basis)),
        current_price=Decimal("0"),
        unrealized_pl=Decimal("0"),
        unrealized_plpc=Decimal("0"),
    )


def _carryover_snapshot():
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
        positions=(
            _position(LONG, 1, "542"),
            _position(SHORT, -1, "-549"),
        ),
        option_contract_units=Decimal("2"),
        managed_spreads=1,
    )


def test_closed_mleg_history_recovers_remaining_open_entry_basis_fifo():
    orders = (
        _order(
            submitted_at=datetime(2026, 9, 16, 14, 0, tzinfo=timezone.utc),
            price="0.53",
        ),
        _order(
            submitted_at=datetime(2026, 9, 16, 15, 0, tzinfo=timezone.utc),
            price="-0.41",
            purpose="exit",
        ),
        _order(
            submitted_at=datetime(2026, 9, 16, 16, 0, tzinfo=timezone.utc),
            price="0.56",
        ),
    )
    client = HistoryClient(reversed(orders))

    basis = read_open_spread_entry_basis(trading_client=client)

    assert basis == {STRUCTURE: Decimal("0.56")}
    assert len(client.filters) == 1
    request = client.filters[0]
    assert request.limit == 500
    assert request.nested is True


def test_filled_entry_can_fall_back_to_positive_parent_limit_debit():
    client = HistoryClient(
        [
            _order(
                submitted_at=datetime(
                    2026, 9, 17, 14, 0, tzinfo=timezone.utc
                ),
                price=None,
                limit_price="0.53",
            )
        ]
    )

    basis = read_open_spread_entry_basis(trading_client=client)

    assert basis == {STRUCTURE: Decimal("0.53")}


def test_recovered_basis_repairs_non_positive_leg_cost_basis_reconstruction():
    spreads = identify_managed_debit_spreads(
        _carryover_snapshot(),
        entry_basis_by_structure={STRUCTURE: Decimal("0.53")},
    )

    assert len(spreads) == 1
    spread = spreads[0]
    assert spread.option_type == "put"
    assert spread.long_symbol == LONG
    assert spread.short_symbol == SHORT
    assert spread.entry_debit_per_contract == Decimal("0.53")


def test_exit_cycle_uses_recovered_basis_for_restart_position():
    class TradingClient:
        def __init__(self):
            self.orders = []

        def submit_order(self, *, order_data):
            self.orders.append(order_data)
            return SimpleNamespace(id="restart-exit-1")

    trading_client = TradingClient()
    result = run_paper_spread_exit_cycle(
        trading_client=trading_client,
        option_data_client=OptionClient(),
        snapshot=_carryover_snapshot(),
        take_profit_percent=Decimal("20"),
        stop_loss_percent=Decimal("20"),
        entry_basis_provider=lambda: {
            STRUCTURE: Decimal("0.53")
        },
    )

    assert result.submitted is True
    assert result.reason == "stop_loss_exit_submitted"
    assert result.entry_debit_per_contract == Decimal("0.53")
    assert result.long_symbol == LONG
    assert result.short_symbol == SHORT


def test_exit_cycle_automatically_queries_history_when_leg_basis_is_invalid():
    class TradingHistoryClient(HistoryClient):
        def __init__(self):
            super().__init__(
                [
                    _order(
                        submitted_at=datetime(
                            2026, 9, 17, 14, 0, tzinfo=timezone.utc
                        ),
                        price="0.53",
                    )
                ]
            )
            self.submitted = []

        def submit_order(self, *, order_data):
            self.submitted.append(order_data)
            return SimpleNamespace(id="automatic-recovery-exit")

    trading_client = TradingHistoryClient()

    result = run_paper_spread_exit_cycle(
        trading_client=trading_client,
        option_data_client=OptionClient(),
        snapshot=_carryover_snapshot(),
        take_profit_percent=Decimal("20"),
        stop_loss_percent=Decimal("20"),
    )

    assert result.submitted is True
    assert result.reason == "stop_loss_exit_submitted"
    assert result.entry_debit_per_contract == Decimal("0.53")
    assert len(trading_client.filters) == 1
    assert len(trading_client.submitted) == 1


def test_missing_restart_basis_fails_closed_instead_of_reporting_no_spread():
    result = run_paper_spread_exit_cycle(
        trading_client=SimpleNamespace(),
        option_data_client=SimpleNamespace(),
        snapshot=_carryover_snapshot(),
        entry_basis_provider=lambda: {},
    )

    assert result.submitted is False
    assert result.block_new_entries is True
    assert result.reason == "managed_spread_entry_basis_unavailable"
