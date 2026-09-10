from decimal import Decimal
from types import SimpleNamespace

from lockean_lite.paper_portfolio_snapshot import (
    PaperPortfolioSnapshot,
    PaperPositionSnapshot,
)
from lockean_lite.position_exit_manager import (
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


def _snapshot():
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
            _position("SPY260918C00762000", 1, "100"),
            _position("SPY260918C00764000", -1, "-50"),
        ),
        option_contract_units=Decimal("2"),
        managed_spreads=1,
    )


class FakeOptionDataClient:
    def get_option_latest_quote(self, request):
        return {
            "SPY260918C00762000": SimpleNamespace(
                bid_price=Decimal("0.90"),
                ask_price=Decimal("0.92"),
            ),
            "SPY260918C00764000": SimpleNamespace(
                bid_price=Decimal("0.20"),
                ask_price=Decimal("0.22"),
            ),
        }


class FakeTradingClient:
    def __init__(self):
        self.orders = []

    def submit_order(self, *, order_data):
        self.orders.append(order_data)
        return SimpleNamespace(id="exit-1")


def test_take_profit_concedes_price_but_never_below_target_return_floor():
    client = FakeTradingClient()

    result = run_paper_spread_exit_cycle(
        trading_client=client,
        option_data_client=FakeOptionDataClient(),
        snapshot=_snapshot(),
        take_profit_percent=Decimal("20"),
        stop_loss_percent=Decimal("20"),
        take_profit_price_concession=Decimal("0.02"),
    )

    # Entry debit is 0.50. Executable close credit is 0.68, or +36%.
    # We may concede two cents for fill quality, but not below the +20%
    # target floor of 0.60.
    assert result.submitted
    assert result.reason == "take_profit_exit_submitted"
    assert result.observed_close_credit == Decimal("0.68")
    assert result.submitted_limit_credit == Decimal("0.66")
    assert result.entry_debit_per_contract == Decimal("0.5")
    assert client.orders[0].limit_price == -0.66


def test_take_profit_concession_does_not_cross_minimum_profit_floor():
    class NearThresholdOptionDataClient:
        def get_option_latest_quote(self, request):
            return {
                "SPY260918C00762000": SimpleNamespace(
                    bid_price=Decimal("0.83"),
                    ask_price=Decimal("0.85"),
                ),
                "SPY260918C00764000": SimpleNamespace(
                    bid_price=Decimal("0.20"),
                    ask_price=Decimal("0.22"),
                ),
            }

    client = FakeTradingClient()
    result = run_paper_spread_exit_cycle(
        trading_client=client,
        option_data_client=NearThresholdOptionDataClient(),
        snapshot=_snapshot(),
        take_profit_percent=Decimal("20"),
        stop_loss_percent=Decimal("20"),
        take_profit_price_concession=Decimal("0.05"),
    )

    assert result.submitted
    assert result.observed_close_credit == Decimal("0.61")
    assert result.submitted_limit_credit == Decimal("0.60")
    assert client.orders[0].limit_price == -0.6
