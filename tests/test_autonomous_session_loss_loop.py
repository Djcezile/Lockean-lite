from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from lockean_lite.autonomous_session import run_autonomous_paper_session
from lockean_lite.paper_portfolio_snapshot import PaperPortfolioSnapshot
from lockean_lite.session_loss_loop_policy import SessionLossLoopState


NOW = datetime(2026, 9, 29, 15, 0, tzinfo=timezone.utc)


def _portfolio(*, managed_spreads=0, pending_entry_units=0):
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
        option_contract_units=Decimal(managed_spreads * 2),
        managed_spreads=managed_spreads,
        pending_entry_spread_units=pending_entry_units,
    )


def _clock():
    return SimpleNamespace(
        is_open=True,
        next_open="next-open",
        next_close=datetime(2026, 9, 29, 20, 0, tzinfo=timezone.utc),
    )


def _exit_result():
    return SimpleNamespace(
        submitted=False,
        reason="no_managed_spread_detected",
        broker_order_id=None,
        expected_return_percent=None,
        block_new_entries=False,
        cancelled_order_ids=(),
    )


def _cycle_result():
    return SimpleNamespace(
        status="NO_TRADE",
        reason="agent_declined_trade",
        execution_proof=None,
        diagnostics=(),
    )


def _state(
    *,
    fills,
    remaining_capacity=None,
    direction=None,
    halt=False,
    reason,
):
    if remaining_capacity is None:
        remaining_capacity = max(0, 2 - fills)
    return SessionLossLoopState(
        confirmed_stop_loss_fills=fills,
        remaining_stop_loss_capacity=remaining_capacity,
        blocked_direction=direction,
        cooldown_until=None,
        halt_all_entries=halt,
        reason=reason,
    )


def test_active_direction_cooldown_reaches_proposal_cycle_while_risk_runs():
    exit_calls = []
    cycle_states = []
    state = _state(
        fills=1,
        direction="bullish",
        reason="same_direction_stop_loss_cooldown",
    )

    run_autonomous_paper_session(
        clock_provider=_clock,
        portfolio_provider=_portfolio,
        cycle_runner=lambda *, loss_loop_state: (
            cycle_states.append(loss_loop_state) or _cycle_result()
        ),
        exit_runner=lambda snapshot: (
            exit_calls.append(snapshot) or _exit_result()
        ),
        loss_loop_state_provider=lambda now: state,
        now_fn=lambda: NOW,
        interval_seconds=30,
        risk_check_interval_seconds=30,
        sleep_fn=lambda seconds: None,
        output_fn=lambda message: None,
        max_iterations=1,
    )

    assert len(exit_calls) == 1
    assert cycle_states == [state]


def test_second_stop_fill_halts_entries_but_risk_checks_continue():
    exit_calls = []
    cycle_calls = []
    outputs = []

    summary = run_autonomous_paper_session(
        clock_provider=_clock,
        portfolio_provider=_portfolio,
        cycle_runner=lambda: cycle_calls.append("cycle"),
        exit_runner=lambda snapshot: (
            exit_calls.append(snapshot) or _exit_result()
        ),
        loss_loop_state_provider=lambda now: _state(
            fills=2,
            halt=True,
            reason="session_stop_loss_limit_reached",
        ),
        now_fn=lambda: NOW,
        sleep_fn=lambda seconds: None,
        output_fn=outputs.append,
        max_iterations=1,
    )

    assert len(exit_calls) == 1
    assert cycle_calls == []
    assert summary.last_status == "LOSS_LOOP_ENTRY_BLOCKED"
    assert summary.last_reason == "session_stop_loss_limit_reached"
    assert any("LOSS-LOOP ENTRY GATE: BLOCKED" in line for line in outputs)


def test_first_stop_blocks_second_committed_spread_after_cooldown_expires():
    cycle_calls = []
    outputs = []

    summary = run_autonomous_paper_session(
        clock_provider=_clock,
        portfolio_provider=lambda: _portfolio(managed_spreads=1),
        cycle_runner=lambda **kwargs: cycle_calls.append(kwargs),
        exit_runner=lambda snapshot: _exit_result(),
        loss_loop_state_provider=lambda now: _state(
            fills=1,
            remaining_capacity=1,
            reason="loss_loop_entry_allowed",
        ),
        maximum_open_spreads=2,
        now_fn=lambda: NOW,
        sleep_fn=lambda seconds: None,
        output_fn=outputs.append,
        max_iterations=1,
    )

    assert cycle_calls == []
    assert summary.last_status == "ENTRY_BLOCKED"
    assert summary.last_reason == "session_stop_loss_capacity_reached"
    assert any(
        "PORTFOLIO ENTRY GATE: BLOCKED | "
        "session_stop_loss_capacity_reached" in line
        for line in outputs
    )
    assert any("remaining_stop_capacity=1" in line for line in outputs)


def test_loss_loop_state_failure_blocks_entry_but_not_risk_check():
    exit_calls = []
    cycle_calls = []
    outputs = []

    def unavailable(now):
        raise RuntimeError("broker history unavailable")

    summary = run_autonomous_paper_session(
        clock_provider=_clock,
        portfolio_provider=_portfolio,
        cycle_runner=lambda: cycle_calls.append("cycle"),
        exit_runner=lambda snapshot: (
            exit_calls.append(snapshot) or _exit_result()
        ),
        loss_loop_state_provider=unavailable,
        now_fn=lambda: NOW,
        sleep_fn=lambda seconds: None,
        output_fn=outputs.append,
        max_iterations=1,
    )

    assert len(exit_calls) == 1
    assert cycle_calls == []
    assert summary.last_status == "LOSS_LOOP_STATE_UNAVAILABLE"
    assert any("FAIL CLOSED: no new entry" in line for line in outputs)


def test_loss_loop_block_cancels_pending_entry_before_stale_snapshot_actions():
    exit_calls = []
    cycle_calls = []
    cancel_calls = []

    summary = run_autonomous_paper_session(
        clock_provider=_clock,
        portfolio_provider=lambda: _portfolio(pending_entry_units=1),
        cycle_runner=lambda: cycle_calls.append("cycle"),
        exit_runner=lambda snapshot: (
            exit_calls.append(snapshot) or _exit_result()
        ),
        end_of_day_cancel_runner=lambda snapshot: (
            cancel_calls.append(snapshot) or ("pending-entry",)
        ),
        loss_loop_state_provider=lambda now: _state(
            fills=1,
            direction="bullish",
            reason="same_direction_stop_loss_cooldown",
        ),
        now_fn=lambda: NOW,
        sleep_fn=lambda seconds: None,
        output_fn=lambda message: None,
        max_iterations=1,
    )

    assert len(cancel_calls) == 1
    assert exit_calls == []
    assert cycle_calls == []
    assert summary.last_status == "ENTRY_ORDER_CANCELLED"
    assert summary.last_reason == "loss_loop_pending_entry_cancelled"
