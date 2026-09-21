from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

from lockean_lite.autonomous_session import (
    _cancel_pending_entry_mleg_orders,
    run_autonomous_paper_session,
)
from lockean_lite.paper_portfolio_snapshot import (
    PaperPortfolioSnapshot,
    PendingMlegOrderSnapshot,
)


def _portfolio(*, pending_orders=()):
    pending_entry_units = sum(
        order.remaining_units
        for order in pending_orders
        if order.purpose == "entry"
    )
    pending_exit_units = sum(
        order.remaining_units
        for order in pending_orders
        if order.purpose == "exit"
    )
    pending_unknown_units = sum(
        order.remaining_units
        for order in pending_orders
        if order.purpose == "unknown"
    )

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
        positions=(),
        option_contract_units=Decimal("0"),
        managed_spreads=0,
        pending_spread_units=(
            pending_entry_units
            + pending_exit_units
            + pending_unknown_units
        ),
        pending_entry_spread_units=pending_entry_units,
        pending_exit_spread_units=pending_exit_units,
        pending_unknown_spread_units=pending_unknown_units,
        pending_mleg_orders=tuple(pending_orders),
    )


def _near_close_clock(now):
    return SimpleNamespace(
        is_open=True,
        next_open="next-open",
        next_close=now + timedelta(minutes=3),
    )


def _exit_result(**overrides):
    values = {
        "submitted": False,
        "reason": "no_managed_spread_exit_trigger",
        "broker_order_id": None,
        "expected_return_percent": None,
        "block_new_entries": False,
        "cancelled_order_ids": (),
        "diagnostics": (),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _pending(order_id, purpose):
    return PendingMlegOrderSnapshot(
        order_id=order_id,
        remaining_units=1,
        purpose=purpose,
        submitted_at=datetime(
            2026,
            9,
            21,
            19,
            54,
            tzinfo=timezone.utc,
        ),
        symbols=(
            "SPY260923C00771000",
            "SPY260923C00773000",
        ),
    )


def test_eod_cutoff_runs_position_risk_before_entry_cleanup():
    now = datetime(2026, 9, 21, 19, 57, tzinfo=timezone.utc)
    events = []
    cycle_calls = []

    summary = run_autonomous_paper_session(
        clock_provider=lambda: _near_close_clock(now),
        portfolio_provider=_portfolio,
        cycle_runner=lambda: cycle_calls.append("entry"),
        exit_runner=lambda snapshot: (
            events.append("risk")
            or _exit_result()
        ),
        end_of_day_cancel_runner=lambda snapshot: (
            events.append("cleanup")
            or ()
        ),
        end_of_day_entry_cutoff_minutes=5,
        now_fn=lambda: now,
        interval_seconds=120,
        risk_check_interval_seconds=30,
        sleep_fn=lambda seconds: None,
        output_fn=lambda message: None,
        max_iterations=1,
    )

    assert events == ["risk", "cleanup"]
    assert cycle_calls == []
    assert summary.last_status == "EOD_ENTRY_BLOCKED"
    assert summary.last_reason == "end_of_day_entry_cutoff"


def test_triggered_exit_can_submit_inside_eod_entry_cutoff():
    now = datetime(2026, 9, 21, 19, 57, tzinfo=timezone.utc)
    cleanup_calls = []
    cycle_calls = []

    summary = run_autonomous_paper_session(
        clock_provider=lambda: _near_close_clock(now),
        portfolio_provider=_portfolio,
        cycle_runner=lambda: cycle_calls.append("entry"),
        exit_runner=lambda snapshot: _exit_result(
            submitted=True,
            reason="take_profit_exit_submitted",
            broker_order_id="protective-exit",
            expected_return_percent=Decimal("25.00"),
            block_new_entries=True,
        ),
        end_of_day_cancel_runner=lambda snapshot: (
            cleanup_calls.append("cleanup")
            or ()
        ),
        end_of_day_entry_cutoff_minutes=5,
        now_fn=lambda: now,
        interval_seconds=120,
        risk_check_interval_seconds=30,
        sleep_fn=lambda seconds: None,
        output_fn=lambda message: None,
        max_iterations=1,
    )

    assert cleanup_calls == []
    assert cycle_calls == []
    assert summary.last_status == "EXIT_SUBMITTED"
    assert summary.last_reason == "take_profit_exit_submitted"


def test_eod_cleanup_cancels_only_pending_entry_orders():
    entry = _pending("entry-1", "entry")
    protective_exit = _pending("exit-1", "exit")
    snapshot = _portfolio(
        pending_orders=(entry, protective_exit)
    )

    class TradingClient:
        def __init__(self):
            self.cancelled = []

        def cancel_order_by_id(self, order_id):
            self.cancelled.append(order_id)

    client = TradingClient()

    cancelled = _cancel_pending_entry_mleg_orders(
        trading_client=client,
        snapshot=snapshot,
    )

    assert cancelled == ("entry-1",)
    assert client.cancelled == ["entry-1"]


def test_eod_cleanup_preserves_exit_and_unknown_orders_fail_closed():
    entry = _pending("entry-1", "entry")
    protective_exit = _pending("exit-1", "exit")
    unknown = _pending("unknown-1", "unknown")
    snapshot = _portfolio(
        pending_orders=(entry, protective_exit, unknown)
    )

    class TradingClient:
        def __init__(self):
            self.cancelled = []

        def cancel_order_by_id(self, order_id):
            self.cancelled.append(order_id)

    client = TradingClient()

    try:
        _cancel_pending_entry_mleg_orders(
            trading_client=client,
            snapshot=snapshot,
        )
    except ValueError as error:
        assert str(error) == "pending_mleg_order_purpose_unknown"
    else:
        raise AssertionError("unknown pending MLEG must fail closed")

    assert client.cancelled == []
