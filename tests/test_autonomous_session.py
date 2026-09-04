from decimal import Decimal
from types import SimpleNamespace

from lockean_lite.autonomous_session import (
    run_autonomous_paper_session,
)
from lockean_lite.paper_portfolio_snapshot import (
    PaperPortfolioSnapshot,
)


def _portfolio(*, managed_spreads=0, day_pl=Decimal("0")):
    return PaperPortfolioSnapshot(
        status="ACTIVE",
        currency="USD",
        trading_blocked=False,
        cash=Decimal("100000"),
        equity=Decimal("100000") + day_pl,
        last_equity=Decimal("100000"),
        buying_power=Decimal("200000"),
        options_buying_power=Decimal("100000"),
        portfolio_value=Decimal("100000") + day_pl,
        starting_equity=Decimal("100000"),
        total_pl=day_pl,
        day_pl=day_pl,
        unrealized_pl=day_pl,
        positions=(),
        option_contract_units=Decimal(managed_spreads * 2),
        managed_spreads=managed_spreads,
    )


def _open_clock():
    return SimpleNamespace(
        is_open=True,
        next_open="next-open",
        next_close="next-close",
    )


def _closed_clock():
    return SimpleNamespace(
        is_open=False,
        next_open="next-open",
        next_close="next-close",
    )


def test_session_repeats_autonomous_cycles_while_market_is_open():
    cycle_calls = []
    sleeps = []

    def cycle_runner():
        cycle_calls.append("called")
        return SimpleNamespace(
            status="NO_TRADE",
            reason="agent_declined_trade",
            execution_proof=None,
        )

    summary = run_autonomous_paper_session(
        clock_provider=_open_clock,
        portfolio_provider=lambda: _portfolio(),
        cycle_runner=cycle_runner,
        interval_seconds=5,
        sleep_fn=sleeps.append,
        output_fn=lambda message: None,
        max_iterations=3,
    )

    assert len(cycle_calls) == 3
    assert sleeps == [5, 5]
    assert summary.iterations == 3
    assert summary.trade_cycles == 3
    assert summary.last_status == "NO_TRADE"


def test_session_waits_when_market_is_closed_without_running_agent():
    cycle_calls = []
    sleeps = []

    summary = run_autonomous_paper_session(
        clock_provider=_closed_clock,
        portfolio_provider=lambda: _portfolio(),
        cycle_runner=lambda: cycle_calls.append("called"),
        interval_seconds=300,
        sleep_fn=sleeps.append,
        output_fn=lambda message: None,
        max_iterations=2,
    )

    assert cycle_calls == []
    assert sleeps == [60]
    assert summary.last_reason == "market_closed_waiting_for_open"


def test_session_blocks_new_entries_at_five_spread_units_but_keeps_monitoring():
    cycle_calls = []
    sleeps = []

    summary = run_autonomous_paper_session(
        clock_provider=_open_clock,
        portfolio_provider=lambda: _portfolio(managed_spreads=5),
        cycle_runner=lambda: cycle_calls.append("called"),
        interval_seconds=5,
        maximum_open_spreads=5,
        sleep_fn=sleeps.append,
        output_fn=lambda message: None,
        max_iterations=2,
    )

    assert cycle_calls == []
    assert sleeps == [5]
    assert summary.last_status == "ENTRY_BLOCKED"
    assert summary.last_reason == "portfolio_spread_limit_reached"


def test_session_blocks_new_entries_after_daily_loss_halt():
    cycle_calls = []

    summary = run_autonomous_paper_session(
        clock_provider=_open_clock,
        portfolio_provider=lambda: _portfolio(
            day_pl=Decimal("-800")
        ),
        cycle_runner=lambda: cycle_calls.append("called"),
        maximum_daily_loss=Decimal("750"),
        interval_seconds=1,
        sleep_fn=lambda seconds: None,
        output_fn=lambda message: None,
        max_iterations=1,
    )

    assert cycle_calls == []
    assert summary.last_reason == "daily_loss_limit_reached"


def test_session_reports_broker_order_id_when_execution_proof_exists():
    output = []

    result = SimpleNamespace(
        status="EXECUTED",
        reason="paper_order_submitted",
        execution_proof=SimpleNamespace(
            broker_order_id="broker-123"
        ),
    )

    run_autonomous_paper_session(
        clock_provider=_open_clock,
        portfolio_provider=lambda: _portfolio(),
        cycle_runner=lambda: result,
        interval_seconds=1,
        sleep_fn=lambda seconds: None,
        output_fn=output.append,
        max_iterations=1,
    )

    assert any(
        "ALPACA BROKER ORDER ID: broker-123" in line
        for line in output
    )
