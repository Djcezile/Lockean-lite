from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from lockean_lite.autonomous_session import run_autonomous_paper_session
from lockean_lite.filled_spread_basis import (
    recover_open_spread_entry_basis,
    render_spread_basis_recovery_report,
)
from lockean_lite.paper_portfolio_snapshot import (
    PaperPortfolioSnapshot,
    PaperPositionSnapshot,
)
from lockean_lite.position_exit_manager import run_paper_spread_exit_cycle
from lockean_lite.spread_basis_probe import build_live_probe_report


LONG = "SPY260918P00752000"
SHORT = "SPY260918P00751000"


def _leg(symbol, intent=None):
    return SimpleNamespace(
        symbol=symbol,
        position_intent=intent,
    )


def _order(
    *,
    order_class="mleg",
    legs=(),
    qty=1,
    filled_qty=1,
    filled_avg_price=None,
    limit_price=None,
    submitted_at=None,
):
    return SimpleNamespace(
        order_class=order_class,
        legs=tuple(legs),
        qty=str(qty),
        filled_qty=str(filled_qty),
        filled_avg_price=filled_avg_price,
        limit_price=limit_price,
        submitted_at=(
            submitted_at
            or datetime(2026, 9, 17, 15, 0, tzinfo=timezone.utc)
        ),
    )


class HistoryClient:
    def __init__(self, orders):
        self.orders = list(orders)

    def get_orders(self, *, filter):
        return list(self.orders)


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


def test_recovery_diagnostics_explain_historical_order_shape():
    missing_intent = _order(
        legs=(
            _leg(LONG),
            _leg(SHORT),
        ),
        filled_avg_price="0.50",
    )
    missing_price = _order(
        legs=(
            _leg("SPY260918C00760000", "buy_to_open"),
            _leg("SPY260918C00762000", "sell_to_open"),
        ),
    )
    fallback_price = _order(
        legs=(
            _leg(LONG, "buy_to_open"),
            _leg(SHORT, "sell_to_open"),
        ),
        limit_price="0.53",
    )
    unmatched_exit = _order(
        legs=(
            _leg("SPY260918C00762000", "sell_to_close"),
            _leg("SPY260918C00764000", "buy_to_close"),
        ),
        filled_avg_price="-0.20",
    )

    result = recover_open_spread_entry_basis(
        trading_client=HistoryClient(
            [
                _order(order_class="simple"),
                missing_intent,
                missing_price,
                fallback_price,
                unmatched_exit,
            ]
        )
    )

    diagnostic = result.diagnostics
    assert diagnostic.closed_orders_returned == 5
    assert diagnostic.parsed_mleg_orders == 3
    assert diagnostic.entry_orders_recognized == 2
    assert diagnostic.exit_orders_recognized == 1
    assert diagnostic.missing_position_intent_orders == 1
    assert diagnostic.missing_filled_price_entries == 1
    assert diagnostic.limit_price_fallback_entries == 1
    assert diagnostic.fifo_underflow_structures == 1
    assert diagnostic.recovered_structures == 1
    assert result.basis_by_structure == {
        frozenset({LONG, SHORT}): Decimal("0.53")
    }


def test_probe_report_is_read_only_summary_without_sensitive_account_data():
    result = recover_open_spread_entry_basis(
        trading_client=HistoryClient(
            [
                _order(
                    legs=(
                        _leg(LONG, "buy_to_open"),
                        _leg(SHORT, "sell_to_open"),
                    ),
                    filled_avg_price="0.53",
                )
            ]
        )
    )

    report = render_spread_basis_recovery_report(result)

    assert "closed_orders_returned=1" in report
    assert "entry_orders_recognized=1" in report
    assert "recovered_structures=1" in report
    assert LONG in report
    assert SHORT in report
    assert "api_key" not in report.lower()
    assert "account_id" not in report.lower()


def test_failed_exit_recovery_surfaces_diagnostics_and_open_symbols():
    result = run_paper_spread_exit_cycle(
        trading_client=HistoryClient([]),
        option_data_client=SimpleNamespace(),
        snapshot=_carryover_snapshot(),
    )

    assert result.submitted is False
    assert result.block_new_entries is True
    assert result.reason == "managed_spread_entry_basis_unavailable"
    assert any(
        item == "basis_recovery_closed_orders_returned=0"
        for item in result.diagnostics
    )
    assert any(
        item == f"unrecovered_open_symbols={LONG},{SHORT}"
        or item == f"unrecovered_open_symbols={SHORT},{LONG}"
        for item in result.diagnostics
    )


def test_autonomous_session_logs_exit_recovery_diagnostics_before_blocking():
    messages = []

    exit_result = SimpleNamespace(
        submitted=False,
        reason="managed_spread_entry_basis_unavailable",
        broker_order_id=None,
        expected_return_percent=None,
        block_new_entries=True,
        cancelled_order_ids=(),
        diagnostics=(
            "basis_recovery_closed_orders_returned=7",
            f"unrecovered_open_symbols={LONG},{SHORT}",
        ),
    )

    result = run_autonomous_paper_session(
        clock_provider=lambda: SimpleNamespace(
            is_open=True,
            next_open="next-open",
            next_close="next-close",
        ),
        portfolio_provider=_carryover_snapshot,
        cycle_runner=lambda: None,
        exit_runner=lambda snapshot: exit_result,
        interval_seconds=1,
        sleep_fn=lambda seconds: None,
        output_fn=messages.append,
        max_iterations=1,
    )

    assert result.last_status == "ENTRY_BLOCKED"
    assert (
        "POSITION EXIT DIAGNOSTIC: "
        "basis_recovery_closed_orders_returned=7"
    ) in messages
    assert any(
        message.startswith(
            "POSITION EXIT DIAGNOSTIC: unrecovered_open_symbols="
        )
        for message in messages
    )


def test_live_probe_report_compares_recovered_units_to_open_portfolio():
    recovery = recover_open_spread_entry_basis(
        trading_client=HistoryClient(
            [
                _order(
                    legs=(
                        _leg(LONG, "buy_to_open"),
                        _leg(SHORT, "sell_to_open"),
                    ),
                    filled_avg_price="0.53",
                )
            ]
        )
    )

    report = build_live_probe_report(
        recovery_result=recovery,
        snapshot=_carryover_snapshot(),
    )

    assert "current_managed_spread_units=1" in report
    assert "recovered_managed_spread_units=1" in report
    assert "recovery_matches_open_portfolio=True" in report
    assert f"current_open_option_symbols={SHORT},{LONG}" in report or (
        f"current_open_option_symbols={LONG},{SHORT}" in report
    )
