from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

from lockean_lite.autonomous_session import (
    run_autonomous_paper_session,
)
from lockean_lite.paper_portfolio_snapshot import (
    PaperPortfolioSnapshot,
)


def _portfolio():
    return PaperPortfolioSnapshot(
        status="ACTIVE",
        currency="USD",
        trading_blocked=False,
        cash=Decimal("100000"),
        equity=Decimal("100000"),
        last_equity=Decimal("100000"),
        buying_power=Decimal("200000"),
        options_buying_power=Decimal("100000"),
        portfolio_value=Decimal("100000"),
        starting_equity=Decimal("100000"),
        total_pl=Decimal("0"),
        day_pl=Decimal("0"),
        unrealized_pl=Decimal("0"),
        positions=(),
        option_contract_units=Decimal("0"),
        managed_spreads=0,
    )


def _open_clock():
    return SimpleNamespace(
        is_open=True,
        next_open="next-open",
        next_close="next-close",
    )


def _exit_result(**overrides):
    values = {
        "submitted": False,
        "reason": "no_managed_spread_exit_trigger",
        "broker_order_id": None,
        "expected_return_percent": None,
        "block_new_entries": False,
        "cancelled_order_ids": (),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_submitted_exit_skips_new_entry_until_next_reconciliation_cycle():
    cycle_calls = []

    result = run_autonomous_paper_session(
        clock_provider=_open_clock,
        portfolio_provider=_portfolio,
        cycle_runner=lambda: cycle_calls.append(
            "entry-cycle"
        ),
        exit_runner=lambda snapshot: _exit_result(
            submitted=True,
            reason="take_profit_exit_submitted",
            broker_order_id="exit-123",
            expected_return_percent=Decimal("15.00"),
            block_new_entries=True,
        ),
        interval_seconds=1,
        sleep_fn=lambda seconds: None,
        output_fn=lambda message: None,
        max_iterations=1,
    )

    assert cycle_calls == []
    assert result.last_status == "EXIT_SUBMITTED"
    assert result.last_reason == "take_profit_exit_submitted"


def test_unresolved_exit_state_blocks_new_entry():
    cycle_calls = []

    result = run_autonomous_paper_session(
        clock_provider=_open_clock,
        portfolio_provider=_portfolio,
        cycle_runner=lambda: cycle_calls.append(
            "entry-cycle"
        ),
        exit_runner=lambda snapshot: _exit_result(
            reason="pending_mleg_order_exists",
            block_new_entries=True,
        ),
        interval_seconds=1,
        sleep_fn=lambda seconds: None,
        output_fn=lambda message: None,
        max_iterations=1,
    )

    assert cycle_calls == []
    assert result.last_status == "ENTRY_BLOCKED"
    assert result.last_reason == "pending_mleg_order_exists"


def test_active_pending_exit_can_leave_unrelated_entry_path_available():
    cycle_calls = []

    result = run_autonomous_paper_session(
        clock_provider=_open_clock,
        portfolio_provider=_portfolio,
        cycle_runner=lambda: SimpleNamespace(
            status="NO_TRADE",
            reason="agent_declined_trade",
            execution_proof=None,
        ),
        exit_runner=lambda snapshot: _exit_result(
            reason="pending_exit_order_active",
            block_new_entries=False,
        ),
        interval_seconds=1,
        sleep_fn=lambda seconds: None,
        output_fn=lambda message: cycle_calls.append(message),
        max_iterations=1,
    )

    assert result.trade_cycles == 1
    assert result.last_status == "NO_TRADE"


def test_end_of_day_cutoff_cancels_pending_orders_and_blocks_new_entry():
    cycle_calls = []
    cleanup_calls = []
    now = datetime(2026, 9, 8, 19, 57, tzinfo=timezone.utc)

    clock = SimpleNamespace(
        is_open=True,
        next_open="next-open",
        next_close=now + timedelta(minutes=3),
    )

    result = run_autonomous_paper_session(
        clock_provider=lambda: clock,
        portfolio_provider=_portfolio,
        cycle_runner=lambda: cycle_calls.append("entry"),
        end_of_day_cancel_runner=lambda snapshot: (
            cleanup_calls.append("cleanup")
            or ("pending-1",)
        ),
        end_of_day_entry_cutoff_minutes=5,
        now_fn=lambda: now,
        interval_seconds=1,
        sleep_fn=lambda seconds: None,
        output_fn=lambda message: None,
        max_iterations=1,
    )

    assert cleanup_calls == ["cleanup"]
    assert cycle_calls == []
    assert result.last_status == "EOD_ENTRY_BLOCKED"
    assert result.last_reason == "end_of_day_entry_cutoff"
