from decimal import Decimal
from types import SimpleNamespace

import pytest

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


def _exit_result():
    return SimpleNamespace(
        submitted=False,
        reason="no_managed_spread_exit_trigger",
        broker_order_id=None,
        expected_return_percent=None,
        block_new_entries=False,
        cancelled_order_ids=(),
    )


def _cycle_result(status="NO_TRADE"):
    reason = (
        "paper_order_submitted"
        if status == "SUBMITTED"
        else "agent_declined_trade"
    )
    return SimpleNamespace(
        status=status,
        reason=reason,
        execution_proof=None,
        diagnostics=(),
    )


def test_risk_checks_run_every_30_seconds_while_ai_stays_120_seconds_apart():
    exit_calls = []
    cycle_calls = []
    sleeps = []

    summary = run_autonomous_paper_session(
        clock_provider=_open_clock,
        portfolio_provider=_portfolio,
        cycle_runner=lambda: (
            cycle_calls.append("cycle")
            or _cycle_result()
        ),
        exit_runner=lambda snapshot: (
            exit_calls.append("exit")
            or _exit_result()
        ),
        interval_seconds=120,
        risk_check_interval_seconds=30,
        entry_cooldown_seconds=0,
        sleep_fn=sleeps.append,
        output_fn=lambda message: None,
        max_iterations=5,
    )

    assert len(exit_calls) == 5
    assert len(cycle_calls) == 2
    assert sleeps == [30, 30, 30, 30]
    assert summary.trade_cycles == 2


def test_submitted_entry_starts_cooldown_while_risk_checks_continue():
    exit_calls = []
    cycle_calls = []
    outputs = []

    def cycle_runner():
        cycle_calls.append("cycle")
        if len(cycle_calls) == 1:
            return _cycle_result("SUBMITTED")
        return _cycle_result("NO_TRADE")

    summary = run_autonomous_paper_session(
        clock_provider=_open_clock,
        portfolio_provider=_portfolio,
        cycle_runner=cycle_runner,
        exit_runner=lambda snapshot: (
            exit_calls.append("exit")
            or _exit_result()
        ),
        interval_seconds=30,
        risk_check_interval_seconds=30,
        entry_cooldown_seconds=120,
        sleep_fn=lambda seconds: None,
        output_fn=outputs.append,
        max_iterations=5,
    )

    assert len(exit_calls) == 5
    assert len(cycle_calls) == 2
    assert summary.trade_cycles == 2
    assert any(
        "ENTRY COOLDOWN: ACTIVE" in line
        for line in outputs
    )


def test_no_trade_does_not_start_entry_cooldown():
    cycle_calls = []

    summary = run_autonomous_paper_session(
        clock_provider=_open_clock,
        portfolio_provider=_portfolio,
        cycle_runner=lambda: (
            cycle_calls.append("cycle")
            or _cycle_result("NO_TRADE")
        ),
        interval_seconds=30,
        risk_check_interval_seconds=30,
        entry_cooldown_seconds=120,
        sleep_fn=lambda seconds: None,
        output_fn=lambda message: None,
        max_iterations=3,
    )

    assert len(cycle_calls) == 3
    assert summary.trade_cycles == 3


def test_risk_check_interval_must_be_positive():
    with pytest.raises(
        ValueError,
        match="risk_check_interval_seconds_must_be_positive",
    ):
        run_autonomous_paper_session(
            clock_provider=_open_clock,
            portfolio_provider=_portfolio,
            cycle_runner=lambda: _cycle_result(),
            interval_seconds=120,
            risk_check_interval_seconds=0,
            output_fn=lambda message: None,
            max_iterations=1,
        )


def test_entry_cooldown_must_be_non_negative():
    with pytest.raises(
        ValueError,
        match="entry_cooldown_seconds_must_be_non_negative",
    ):
        run_autonomous_paper_session(
            clock_provider=_open_clock,
            portfolio_provider=_portfolio,
            cycle_runner=lambda: _cycle_result(),
            interval_seconds=120,
            entry_cooldown_seconds=-1,
            output_fn=lambda message: None,
            max_iterations=1,
        )
