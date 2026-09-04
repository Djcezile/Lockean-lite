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


def test_submitted_exit_skips_new_entry_until_next_reconciliation_cycle():
    cycle_calls = []

    result = run_autonomous_paper_session(
        clock_provider=_open_clock,
        portfolio_provider=_portfolio,
        cycle_runner=lambda: cycle_calls.append(
            "entry-cycle"
        ),
        exit_runner=lambda snapshot: SimpleNamespace(
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
    assert result.last_reason == (
        "take_profit_exit_submitted"
    )


def test_unresolved_exit_state_blocks_new_entry():
    cycle_calls = []

    result = run_autonomous_paper_session(
        clock_provider=_open_clock,
        portfolio_provider=_portfolio,
        cycle_runner=lambda: cycle_calls.append(
            "entry-cycle"
        ),
        exit_runner=lambda snapshot: SimpleNamespace(
            submitted=False,
            reason="pending_mleg_order_exists",
            broker_order_id=None,
            expected_return_percent=None,
            block_new_entries=True,
        ),
        interval_seconds=1,
        sleep_fn=lambda seconds: None,
        output_fn=lambda message: None,
        max_iterations=1,
    )

    assert cycle_calls == []
    assert result.last_status == "ENTRY_BLOCKED"
    assert result.last_reason == (
        "pending_mleg_order_exists"
    )
