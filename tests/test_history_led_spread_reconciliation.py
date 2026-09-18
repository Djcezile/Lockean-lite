from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from lockean_lite.filled_spread_basis import (
    recover_open_spread_entry_basis,
)
from lockean_lite.paper_portfolio_snapshot import (
    PaperPortfolioSnapshot,
    PaperPositionSnapshot,
)
from lockean_lite.position_exit_manager import (
    identify_history_reconciled_debit_spreads,
    run_paper_spread_exit_cycle,
)


CALL_LONG = "SPY260918C00762000"
CALL_SHORT = "SPY260918C00764000"
PUT_ORPHAN_SHORT = "SPY260918P00751000"
PUT_ORPHAN_LONG = "SPY260918P00752000"
PUT_A_SHORT = "SPY260918P00750000"
PUT_B_LONG = "SPY260918P00753000"


def _leg(symbol, intent):
    return SimpleNamespace(symbol=symbol, position_intent=intent)


def _entry(long_symbol, short_symbol, debit, submitted_at):
    return SimpleNamespace(
        order_class="mleg",
        legs=(
            _leg(long_symbol, "buy_to_open"),
            _leg(short_symbol, "sell_to_open"),
        ),
        qty="1",
        filled_qty="1",
        filled_avg_price=str(debit),
        limit_price=str(debit),
        submitted_at=submitted_at,
    )


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
            _position(CALL_LONG, 1, "171"),
            _position(CALL_SHORT, -1, "-92"),
            _position(PUT_ORPHAN_LONG, 1, "542"),
            _position(PUT_ORPHAN_SHORT, -1, "-549"),
        ),
        option_contract_units=Decimal("4"),
        managed_spreads=2,
    )


class TradingClient:
    def __init__(self):
        self.submitted = []
        self.orders = [
            _entry(
                CALL_LONG,
                CALL_SHORT,
                "0.79",
                datetime(2026, 9, 17, 14, 0, tzinfo=timezone.utc),
            ),
            # These are the true historical put structures. Current net
            # inventory contains only one leg from each, so 752P/751P must
            # never be invented as a synthetic spread.
            _entry(
                PUT_ORPHAN_LONG,
                PUT_A_SHORT,
                "1.01",
                datetime(2026, 9, 17, 14, 5, tzinfo=timezone.utc),
            ),
            _entry(
                PUT_B_LONG,
                PUT_ORPHAN_SHORT,
                "1.16",
                datetime(2026, 9, 17, 14, 10, tzinfo=timezone.utc),
            ),
        ]

    def get_orders(self, *, filter):
        return list(self.orders)

    def submit_order(self, *, order_data):
        self.submitted.append(order_data)
        return SimpleNamespace(id="history-led-exit")


class OptionClient:
    def get_option_latest_quote(self, request):
        return {
            CALL_LONG: SimpleNamespace(
                bid_price="0.50",
                ask_price="0.51",
            ),
            CALL_SHORT: SimpleNamespace(
                bid_price="0.08",
                ask_price="0.09",
            ),
        }


def test_recovery_exposes_surviving_lot_count_per_exact_structure():
    result = recover_open_spread_entry_basis(
        trading_client=TradingClient()
    )

    assert result.open_lots_by_structure[
        frozenset({CALL_LONG, CALL_SHORT})
    ] == (Decimal("0.79"),)
    assert result.open_lots_by_structure[
        frozenset({PUT_ORPHAN_LONG, PUT_A_SHORT})
    ] == (Decimal("1.01"),)
    assert result.open_lots_by_structure[
        frozenset({PUT_B_LONG, PUT_ORPHAN_SHORT})
    ] == (Decimal("1.16"),)


def test_history_reconciliation_never_pairs_orphan_put_legs_into_synthetic_vertical():
    recovery = recover_open_spread_entry_basis(
        trading_client=TradingClient()
    )

    result = identify_history_reconciled_debit_spreads(
        snapshot=_snapshot(),
        recovery_result=recovery,
    )

    assert len(result.spreads) == 1
    spread = result.spreads[0]
    assert spread.long_symbol == CALL_LONG
    assert spread.short_symbol == CALL_SHORT
    assert spread.entry_debit_per_contract == Decimal("0.79")

    assert PUT_ORPHAN_LONG in result.unreconciled_option_symbols
    assert PUT_ORPHAN_SHORT in result.unreconciled_option_symbols
    assert not any(
        {
            item.long_symbol,
            item.short_symbol,
        } == {
            PUT_ORPHAN_LONG,
            PUT_ORPHAN_SHORT,
        }
        for item in result.spreads
    )


def test_intact_history_spread_can_exit_while_orphan_inventory_blocks_new_entries():
    trading_client = TradingClient()

    result = run_paper_spread_exit_cycle(
        trading_client=trading_client,
        option_data_client=OptionClient(),
        snapshot=_snapshot(),
        take_profit_percent=Decimal("20"),
        stop_loss_percent=Decimal("20"),
    )

    # 0.41 executable credit versus 0.79 entry debit is a stop.
    assert result.submitted is True
    assert result.reason == "stop_loss_exit_submitted"
    assert result.long_symbol == CALL_LONG
    assert result.short_symbol == CALL_SHORT
    assert len(trading_client.submitted) == 1
    assert any(
        diagnostic.startswith("unreconciled_open_option_symbols=")
        for diagnostic in result.diagnostics
    )


def test_orphan_inventory_blocks_entries_when_no_intact_spread_needs_exit():
    class NoExitOptionClient:
        def get_option_latest_quote(self, request):
            return {
                CALL_LONG: SimpleNamespace(
                    bid_price="0.78",
                    ask_price="0.79",
                ),
                CALL_SHORT: SimpleNamespace(
                    bid_price="0.09",
                    ask_price="0.10",
                ),
            }

    result = run_paper_spread_exit_cycle(
        trading_client=TradingClient(),
        option_data_client=NoExitOptionClient(),
        snapshot=_snapshot(),
        take_profit_percent=Decimal("20"),
        stop_loss_percent=Decimal("20"),
    )

    assert result.submitted is False
    assert result.block_new_entries is True
    assert result.reason == "managed_spread_inventory_unreconciled"
    assert any(
        diagnostic.startswith("unreconciled_open_option_symbols=")
        for diagnostic in result.diagnostics
    )
