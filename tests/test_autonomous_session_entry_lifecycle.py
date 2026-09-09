from decimal import Decimal
from types import SimpleNamespace

from lockean_lite.autonomous_session import (
    run_autonomous_paper_session,
)
from lockean_lite.paper_portfolio_snapshot import (
    PaperPortfolioSnapshot,
)
from lockean_lite.pending_entry_manager import (
    PendingEntryMaintenanceResult,
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


def _cycle_result():
    return SimpleNamespace(
        status="NO_TRADE",
        reason="agent_declined_trade",
        execution_proof=None,
    )


def test_cancelled_stale_entry_skips_new_proposal_until_reconciliation():
    cycle_calls = []
    output = []

    summary = run_autonomous_paper_session(
        clock_provider=_open_clock,
        portfolio_provider=_portfolio,
        cycle_runner=lambda: cycle_calls.append("cycle"),
        entry_order_maintenance_runner=lambda snapshot: (
            PendingEntryMaintenanceResult(
                reason="stale_entry_order_cancelled",
                cancelled_order_ids=("entry-1",),
            )
        ),
        interval_seconds=1,
        sleep_fn=lambda seconds: None,
        output_fn=output.append,
        max_iterations=1,
    )

    assert cycle_calls == []
    assert summary.last_status == "ENTRY_ORDER_CANCELLED"
    assert summary.last_reason == "stale_entry_order_cancelled"
    assert any(
        "ENTRY ORDER: CANCELLED | stale_entry_order_cancelled | entry-1"
        in line
        for line in output
    )
    assert any(
        "awaiting broker reconciliation"
        in line
        for line in output
    )


def test_active_entry_order_is_logged_without_forcing_global_block():
    output = []

    summary = run_autonomous_paper_session(
        clock_provider=_open_clock,
        portfolio_provider=_portfolio,
        cycle_runner=_cycle_result,
        entry_order_maintenance_runner=lambda snapshot: (
            PendingEntryMaintenanceResult(
                reason="pending_entry_order_active",
                active_order_ids=("entry-live",),
            )
        ),
        interval_seconds=1,
        sleep_fn=lambda seconds: None,
        output_fn=output.append,
        max_iterations=1,
    )

    assert summary.trade_cycles == 1
    assert summary.last_status == "NO_TRADE"
    assert any(
        "ENTRY ORDER: ACTIVE | pending_entry_order_active | entry-live"
        in line
        for line in output
    )


def test_non_action_exit_reason_is_visible_in_session_log():
    output = []

    summary = run_autonomous_paper_session(
        clock_provider=_open_clock,
        portfolio_provider=_portfolio,
        cycle_runner=_cycle_result,
        exit_runner=lambda snapshot: SimpleNamespace(
            submitted=False,
            reason="no_managed_spread_detected",
            broker_order_id=None,
            expected_return_percent=None,
            block_new_entries=False,
            cancelled_order_ids=(),
        ),
        interval_seconds=1,
        sleep_fn=lambda seconds: None,
        output_fn=output.append,
        max_iterations=1,
    )

    assert summary.last_status == "NO_TRADE"
    assert any(
        "POSITION EXIT CHECK: no_managed_spread_detected"
        in line
        for line in output
    )
