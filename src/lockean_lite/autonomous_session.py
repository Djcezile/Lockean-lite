import argparse
import os
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from alpaca.data.historical import OptionHistoricalDataClient

from lockean_lite.alpaca_client_factory import (
    create_paper_trading_client_from_environment,
)
from lockean_lite.alpaca_credentials import (
    load_alpaca_credentials_from_environment,
)
from lockean_lite.paper_portfolio_snapshot import (
    COMPETITION_STARTING_EQUITY,
    read_live_paper_portfolio_snapshot,
    render_paper_portfolio_snapshot,
)
from lockean_lite.pending_entry_manager import maintain_pending_entry_orders
from lockean_lite.portfolio_gate import evaluate_portfolio_entry
from lockean_lite.position_exit_manager import run_paper_spread_exit_cycle
from lockean_lite.production_runtime import run_live_production_autonomous_cycle
from lockean_lite.safe_error_reporting import safe_exception_reason


DEFAULT_INTERVAL_SECONDS = 300
DEFAULT_RISK_CHECK_INTERVAL_SECONDS = 30
DEFAULT_ENTRY_COOLDOWN_SECONDS = 600
DEFAULT_MAXIMUM_OPEN_SPREADS = 5
DEFAULT_MAXIMUM_DAILY_LOSS = Decimal("750.00")
# Log Days 1-3 used deliberately loose lifecycle-testing thresholds. Now that
# the full autonomous lifecycle is proven, use a symmetric experimental
# payoff policy rather than the old +5/-35 style configuration.
DEFAULT_TAKE_PROFIT_PERCENT = Decimal("20.00")
DEFAULT_STOP_LOSS_PERCENT = Decimal("20.00")
DEFAULT_TAKE_PROFIT_PRICE_CONCESSION = Decimal("0.02")
DEFAULT_MAXIMUM_SAME_STRUCTURE_UNITS = 2
DEFAULT_EXIT_ORDER_TIMEOUT_SECONDS = 240
DEFAULT_ENTRY_ORDER_TIMEOUT_SECONDS = 240
DEFAULT_EOD_ENTRY_CUTOFF_MINUTES = 5

_ENTRY_EVIDENCE_WAIT_REASONS = frozenset(
    {
        "spy_completed_session_missing",
        "vix_completed_session_missing",
        "vix_evidence_unavailable",
    }
)


@dataclass(frozen=True)
class AutonomousSessionSummary:
    iterations: int
    trade_cycles: int
    last_status: str
    last_reason: str


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _seconds_until_market_close(*, clock, now: datetime) -> float | None:
    next_close = getattr(clock, "next_close", None)
    if not isinstance(next_close, datetime):
        return None
    return (
        _normalize_datetime(next_close) - _normalize_datetime(now)
    ).total_seconds()


def _cancel_pending_entry_mleg_orders(
    *,
    trading_client,
    snapshot,
) -> tuple[str, ...]:
    pending_orders = tuple(
        getattr(snapshot, "pending_mleg_orders", ())
    )

    # Unknown purpose means Lockean cannot prove that cancellation would only
    # reduce prospective exposure. Validate the whole snapshot before sending
    # any cancellation so cleanup itself is atomic and fail-closed.
    if any(
        order.purpose == "unknown"
        for order in pending_orders
    ):
        raise ValueError("pending_mleg_order_purpose_unknown")

    entry_orders = tuple(
        order
        for order in pending_orders
        if order.purpose == "entry"
    )

    if any(not order.order_id for order in entry_orders):
        raise ValueError("pending_entry_order_id_missing")

    cancelled_ids = []
    for order in entry_orders:
        trading_client.cancel_order_by_id(order.order_id)
        cancelled_ids.append(order.order_id)

    return tuple(cancelled_ids)


def _cancel_pending_mleg_orders(*, trading_client, snapshot) -> tuple[str, ...]:
    """Compatibility wrapper: EOD cleanup now cancels entries only."""

    return _cancel_pending_entry_mleg_orders(
        trading_client=trading_client,
        snapshot=snapshot,
    )


def _run_eod_entry_cleanup(
    *,
    snapshot,
    end_of_day_cancel_runner,
    output_fn,
) -> str | None:
    cleanup_error_reason = None

    if end_of_day_cancel_runner is not None:
        try:
            cancelled_ids = end_of_day_cancel_runner(snapshot)
        except Exception as error:
            cleanup_error_reason = safe_exception_reason(error)
            output_fn(
                "EOD ORDER CLEANUP: ERROR | "
                f"{type(error).__name__} | {cleanup_error_reason}"
            )
            output_fn(
                "FAIL CLOSED: no new entry near market close"
            )
        else:
            if cancelled_ids:
                output_fn(
                    "EOD ORDER CLEANUP: CANCELLED ENTRY | "
                    + ",".join(cancelled_ids)
                )
            else:
                output_fn(
                    "EOD ORDER CLEANUP: "
                    "NO PENDING ENTRY MLEG ORDERS"
                )

    output_fn(
        "EOD ENTRY CUTOFF: no new positions will be opened; "
        "position risk checks remain active"
    )

    return cleanup_error_reason


def _summary(*, iterations, trade_cycles, last_status, last_reason):
    return AutonomousSessionSummary(
        iterations=iterations,
        trade_cycles=trade_cycles,
        last_status=last_status,
        last_reason=last_reason,
    )


def _log_exit_pricing(output_fn, exit_result) -> None:
    observed_credit = getattr(exit_result, "observed_close_credit", None)
    submitted_credit = getattr(exit_result, "submitted_limit_credit", None)
    entry_debit = getattr(exit_result, "entry_debit_per_contract", None)
    limit_return = getattr(exit_result, "submitted_limit_return_percent", None)
    contracts = getattr(exit_result, "contracts", None)
    long_symbol = getattr(exit_result, "long_symbol", None)
    short_symbol = getattr(exit_result, "short_symbol", None)

    if observed_credit is None or submitted_credit is None:
        return

    details = (
        "POSITION EXIT PRICING: "
        f"entry_debit={entry_debit} | "
        f"observed_credit={observed_credit} | "
        f"submitted_limit_credit={submitted_credit} | "
        f"limit_return={limit_return}% | "
        f"contracts={contracts}"
    )
    if long_symbol and short_symbol:
        details += f" | structure={long_symbol}/{short_symbol}"
    output_fn(details)


def _next_check_message(*, risk_interval: int, entry_interval: int) -> str:
    if risk_interval == entry_interval:
        return f"NEXT AUTONOMOUS CHECK IN {risk_interval} SECONDS"
    return f"NEXT RISK CHECK IN {risk_interval} SECONDS"


def run_autonomous_paper_session(
    *,
    clock_provider,
    portfolio_provider,
    cycle_runner,
    exit_runner=None,
    entry_order_maintenance_runner=None,
    end_of_day_cancel_runner=None,
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    risk_check_interval_seconds: int | None = None,
    entry_cooldown_seconds: int = 0,
    maximum_open_spreads: int = DEFAULT_MAXIMUM_OPEN_SPREADS,
    maximum_daily_loss: Decimal = DEFAULT_MAXIMUM_DAILY_LOSS,
    end_of_day_entry_cutoff_minutes: int = DEFAULT_EOD_ENTRY_CUTOFF_MINUTES,
    new_entries_enabled: bool = True,
    now_fn=None,
    sleep_fn=time.sleep,
    output_fn=print,
    max_iterations: int | None = None,
) -> AutonomousSessionSummary:
    if interval_seconds <= 0:
        raise ValueError("interval_seconds_must_be_positive")

    if risk_check_interval_seconds is None:
        risk_check_interval_seconds = interval_seconds
    if risk_check_interval_seconds <= 0:
        raise ValueError("risk_check_interval_seconds_must_be_positive")
    if entry_cooldown_seconds < 0:
        raise ValueError("entry_cooldown_seconds_must_be_non_negative")
    if end_of_day_entry_cutoff_minutes < 0:
        raise ValueError("end_of_day_entry_cutoff_minutes_must_be_non_negative")

    iterations = 0
    trade_cycles = 0
    last_status = "WAITING"
    last_reason = "session_not_started"
    market_has_opened = False

    # This elapsed-session clock advances by the amount actually slept. It
    # keeps entry scheduling deterministic in tests while matching wall-clock
    # cadence in production, where sleep_fn is time.sleep.
    elapsed_seconds = 0.0
    next_entry_check_at = 0.0
    entry_cooldown_until = 0.0

    output_fn("LOCKEAN AUTONOMOUS PAPER SESSION")
    output_fn("===============================")
    output_fn("MODE: ALPACA PAPER ONLY")
    output_fn(f"MAX MANAGED SPREAD UNITS: {maximum_open_spreads}")
    output_fn(f"DAILY LOSS HALT: -${maximum_daily_loss:.2f}")
    output_fn(f"AI ENTRY CADENCE: {interval_seconds} seconds")
    output_fn(
        "POSITION RISK CADENCE: "
        f"{risk_check_interval_seconds} seconds"
    )
    output_fn(f"POST-SUBMISSION ENTRY COOLDOWN: {entry_cooldown_seconds} seconds")
    output_fn(
        "END-OF-DAY ENTRY CUTOFF: "
        f"{end_of_day_entry_cutoff_minutes} minutes"
    )
    output_fn(
        "NEW ENTRY AUTHORITY: "
        + (
            "ENABLED"
            if new_entries_enabled
            else "DISABLED (RISK MANAGEMENT ONLY)"
        )
    )

    next_check_message = _next_check_message(
        risk_interval=risk_check_interval_seconds,
        entry_interval=interval_seconds,
    )

    while True:
        iterations += 1

        try:
            clock = clock_provider()
            snapshot = portfolio_provider()
        except Exception as error:
            last_status = "STATE_UNAVAILABLE"
            last_reason = safe_exception_reason(error)
            output_fn("")
            output_fn(
                "ALPACA SESSION STATE: UNAVAILABLE | "
                f"{type(error).__name__} | {last_reason}"
            )
            output_fn("FAIL CLOSED: no autonomous order attempt")
            if max_iterations is not None and iterations >= max_iterations:
                return _summary(
                    iterations=iterations,
                    trade_cycles=trade_cycles,
                    last_status=last_status,
                    last_reason=last_reason,
                )
            wait_seconds = min(risk_check_interval_seconds, 60)
            sleep_fn(wait_seconds)
            elapsed_seconds += wait_seconds
            continue

        output_fn("")
        output_fn(render_paper_portfolio_snapshot(snapshot))
        output_fn("")
        output_fn(
            "ALPACA MARKET CLOCK: "
            f"{'OPEN' if clock.is_open else 'CLOSED'}"
        )

        if not clock.is_open:
            if market_has_opened:
                last_status = "SESSION_COMPLETE"
                last_reason = "market_closed"
                output_fn("MARKET CLOSED: autonomous session complete")
                return _summary(
                    iterations=iterations,
                    trade_cycles=trade_cycles,
                    last_status=last_status,
                    last_reason=last_reason,
                )

            last_status = "WAITING"
            last_reason = "market_closed_waiting_for_open"
            output_fn(f"NEXT MARKET OPEN: {clock.next_open}")
            if max_iterations is not None and iterations >= max_iterations:
                return _summary(
                    iterations=iterations,
                    trade_cycles=trade_cycles,
                    last_status=last_status,
                    last_reason=last_reason,
                )
            wait_seconds = min(risk_check_interval_seconds, 60)
            sleep_fn(wait_seconds)
            elapsed_seconds += wait_seconds
            continue

        market_has_opened = True
        current_time = now_fn() if now_fn is not None else datetime.now(timezone.utc)
        seconds_to_close = _seconds_until_market_close(
            clock=clock,
            now=current_time,
        )
        cutoff_seconds = end_of_day_entry_cutoff_minutes * 60

        eod_entry_cutoff_active = (
            seconds_to_close is not None
            and seconds_to_close <= cutoff_seconds
        )

        # Risk-management-only operation must not leave an already-working
        # entry order capable of adding exposure. Cancel it first, then wait
        # for a fresh broker snapshot before acting on existing positions.
        if not new_entries_enabled:
            pending_entry_units = int(
                getattr(
                    snapshot,
                    "pending_entry_spread_units",
                    0,
                )
            )

            if pending_entry_units > 0:
                if end_of_day_cancel_runner is None:
                    last_status = "ENTRY_ORDER_ERROR"
                    last_reason = (
                        "risk_management_only_entry_cleanup_unavailable"
                    )
                    output_fn(
                        "RISK-ONLY ENTRY CLEANUP: ERROR | "
                        f"{last_reason}"
                    )
                    output_fn(
                        "FAIL CLOSED: no AI entry or stale-snapshot "
                        "position action"
                    )
                else:
                    try:
                        cancelled_ids = end_of_day_cancel_runner(
                            snapshot
                        )
                    except Exception as error:
                        last_status = "ENTRY_ORDER_ERROR"
                        last_reason = safe_exception_reason(error)
                        output_fn(
                            "RISK-ONLY ENTRY CLEANUP: ERROR | "
                            f"{type(error).__name__} | {last_reason}"
                        )
                        output_fn(
                            "FAIL CLOSED: no AI entry or stale-snapshot "
                            "position action"
                        )
                    else:
                        if cancelled_ids:
                            last_status = "ENTRY_ORDER_CANCELLED"
                            last_reason = (
                                "risk_management_only_entry_cancelled"
                            )
                            output_fn(
                                "RISK-ONLY ENTRY CLEANUP: CANCELLED | "
                                + ",".join(cancelled_ids)
                            )
                        else:
                            last_status = "ENTRY_ORDER_RECONCILIATION"
                            last_reason = (
                                "risk_management_only_pending_entry_"
                                "reconciliation"
                            )
                            output_fn(
                                "RISK-ONLY ENTRY CLEANUP: WAITING | "
                                f"{last_reason}"
                            )

                if max_iterations is not None and iterations >= max_iterations:
                    return _summary(
                        iterations=iterations,
                        trade_cycles=trade_cycles,
                        last_status=last_status,
                        last_reason=last_reason,
                    )

                output_fn(next_check_message)
                sleep_fn(risk_check_interval_seconds)
                elapsed_seconds += risk_check_interval_seconds
                continue

        # Risk and reconciliation are intentionally evaluated on every loop,
        # including the final entry-cutoff window. EOD policy may stop new
        # exposure, but it must never suspend management of existing risk.
        # Fresh AI entry decisions are scheduled independently below.
        if exit_runner is not None:
            try:
                exit_result = exit_runner(snapshot)
            except Exception as error:
                last_status = "EXIT_ERROR"
                last_reason = safe_exception_reason(error)
                output_fn(
                    "POSITION EXIT CHECK: ERROR | "
                    f"{type(error).__name__} | {last_reason}"
                )
                output_fn(
                    "FAIL CLOSED: no new entry while exit state is unavailable"
                )
                if eod_entry_cutoff_active:
                    _run_eod_entry_cleanup(
                        snapshot=snapshot,
                        end_of_day_cancel_runner=end_of_day_cancel_runner,
                        output_fn=output_fn,
                    )
                if max_iterations is not None and iterations >= max_iterations:
                    return _summary(
                        iterations=iterations,
                        trade_cycles=trade_cycles,
                        last_status=last_status,
                        last_reason=last_reason,
                    )
                output_fn(next_check_message)
                sleep_fn(risk_check_interval_seconds)
                elapsed_seconds += risk_check_interval_seconds
                continue

            for diagnostic in getattr(exit_result, "diagnostics", ()):
                output_fn(
                    "POSITION EXIT DIAGNOSTIC: "
                    f"{diagnostic}"
                )

            if getattr(exit_result, "cancelled_order_ids", ()):
                output_fn(
                    "POSITION EXIT ORDER: CANCELLED | "
                    f"{exit_result.reason} | "
                    + ",".join(exit_result.cancelled_order_ids)
                )

            if exit_result.submitted:
                last_status = "EXIT_SUBMITTED"
                last_reason = exit_result.reason
                return_text = ""
                if exit_result.expected_return_percent is not None:
                    return_text = (
                        " | executable_return="
                        f"{exit_result.expected_return_percent:.2f}%"
                    )
                output_fn(
                    "POSITION EXIT: SUBMITTED | "
                    f"{exit_result.reason}{return_text}"
                )
                _log_exit_pricing(output_fn, exit_result)
                if exit_result.broker_order_id is not None:
                    output_fn(f"ALPACA EXIT ORDER ID: {exit_result.broker_order_id}")
                if eod_entry_cutoff_active:
                    _run_eod_entry_cleanup(
                        snapshot=snapshot,
                        end_of_day_cancel_runner=end_of_day_cancel_runner,
                        output_fn=output_fn,
                    )
                if max_iterations is not None and iterations >= max_iterations:
                    return _summary(
                        iterations=iterations,
                        trade_cycles=trade_cycles,
                        last_status=last_status,
                        last_reason=last_reason,
                    )
                output_fn(next_check_message)
                sleep_fn(risk_check_interval_seconds)
                elapsed_seconds += risk_check_interval_seconds
                continue

            if exit_result.block_new_entries:
                last_status = "ENTRY_BLOCKED"
                last_reason = exit_result.reason
                output_fn(
                    "POSITION EXIT CHECK: BLOCKING NEW ENTRY | "
                    f"{exit_result.reason}"
                )
                if eod_entry_cutoff_active:
                    _run_eod_entry_cleanup(
                        snapshot=snapshot,
                        end_of_day_cancel_runner=end_of_day_cancel_runner,
                        output_fn=output_fn,
                    )
                if max_iterations is not None and iterations >= max_iterations:
                    return _summary(
                        iterations=iterations,
                        trade_cycles=trade_cycles,
                        last_status=last_status,
                        last_reason=last_reason,
                    )
                output_fn(next_check_message)
                sleep_fn(risk_check_interval_seconds)
                elapsed_seconds += risk_check_interval_seconds
                continue

            output_fn(f"POSITION EXIT CHECK: {exit_result.reason}")

        if eod_entry_cutoff_active:
            last_status = "EOD_ENTRY_BLOCKED"
            last_reason = "end_of_day_entry_cutoff"
            cleanup_error_reason = _run_eod_entry_cleanup(
                snapshot=snapshot,
                end_of_day_cancel_runner=end_of_day_cancel_runner,
                output_fn=output_fn,
            )
            if cleanup_error_reason is not None:
                last_reason = cleanup_error_reason

            if max_iterations is not None and iterations >= max_iterations:
                return _summary(
                    iterations=iterations,
                    trade_cycles=trade_cycles,
                    last_status=last_status,
                    last_reason=last_reason,
                )

            output_fn(next_check_message)
            sleep_fn(risk_check_interval_seconds)
            elapsed_seconds += risk_check_interval_seconds
            continue

        if not new_entries_enabled:
            last_status = "RISK_MANAGEMENT_ONLY"
            last_reason = "new_entries_disabled"
            output_fn(
                "ENTRY AUTHORITY: DISABLED | risk_management_only"
            )

            if max_iterations is not None and iterations >= max_iterations:
                return _summary(
                    iterations=iterations,
                    trade_cycles=trade_cycles,
                    last_status=last_status,
                    last_reason=last_reason,
                )

            output_fn(next_check_message)
            sleep_fn(risk_check_interval_seconds)
            elapsed_seconds += risk_check_interval_seconds
            continue

        if entry_order_maintenance_runner is not None:
            try:
                entry_order_result = entry_order_maintenance_runner(snapshot)
            except Exception as error:
                last_status = "ENTRY_ORDER_ERROR"
                last_reason = safe_exception_reason(error)
                output_fn(
                    "ENTRY ORDER MAINTENANCE: ERROR | "
                    f"{type(error).__name__} | {last_reason}"
                )
                output_fn(
                    "FAIL CLOSED: no new entry while pending entry state is unavailable"
                )
                if max_iterations is not None and iterations >= max_iterations:
                    return _summary(
                        iterations=iterations,
                        trade_cycles=trade_cycles,
                        last_status=last_status,
                        last_reason=last_reason,
                    )
                output_fn(next_check_message)
                sleep_fn(risk_check_interval_seconds)
                elapsed_seconds += risk_check_interval_seconds
                continue

            if entry_order_result.cancelled_order_ids:
                last_status = "ENTRY_ORDER_CANCELLED"
                last_reason = entry_order_result.reason
                output_fn(
                    "ENTRY ORDER: CANCELLED | "
                    f"{entry_order_result.reason} | "
                    + ",".join(entry_order_result.cancelled_order_ids)
                )
                output_fn(
                    "ENTRY ORDER: awaiting broker reconciliation before new proposal"
                )
                if max_iterations is not None and iterations >= max_iterations:
                    return _summary(
                        iterations=iterations,
                        trade_cycles=trade_cycles,
                        last_status=last_status,
                        last_reason=last_reason,
                    )
                output_fn(next_check_message)
                sleep_fn(risk_check_interval_seconds)
                elapsed_seconds += risk_check_interval_seconds
                continue

            if entry_order_result.active_order_ids:
                output_fn(
                    "ENTRY ORDER: ACTIVE | "
                    f"{entry_order_result.reason} | "
                    + ",".join(entry_order_result.active_order_ids)
                )

        entry_due = elapsed_seconds >= next_entry_check_at
        cooldown_active = elapsed_seconds < entry_cooldown_until

        if entry_due and cooldown_active:
            remaining = max(0, int(entry_cooldown_until - elapsed_seconds))
            last_status = "ENTRY_COOLDOWN"
            last_reason = "post_submission_entry_cooldown"
            output_fn(
                "ENTRY COOLDOWN: ACTIVE | "
                f"remaining_seconds={remaining}"
            )
        elif entry_due:
            entry_decision = evaluate_portfolio_entry(
                snapshot=snapshot,
                maximum_open_spreads=maximum_open_spreads,
                maximum_daily_loss=maximum_daily_loss,
            )

            if not entry_decision.allowed:
                last_status = "ENTRY_BLOCKED"
                last_reason = entry_decision.reason
                output_fn(
                    "PORTFOLIO ENTRY GATE: BLOCKED | "
                    f"{entry_decision.reason}"
                )
                next_entry_check_at = elapsed_seconds + interval_seconds
            else:
                trade_cycles += 1
                next_entry_check_at = elapsed_seconds + interval_seconds
                try:
                    cycle_result = cycle_runner()
                except Exception as error:
                    last_reason = safe_exception_reason(error)
                    if (
                        isinstance(error, ValueError)
                        and last_reason in _ENTRY_EVIDENCE_WAIT_REASONS
                    ):
                        last_status = "ENTRY_EVIDENCE_WAIT"
                        output_fn(
                            "AUTONOMOUS CYCLE: WAITING | "
                            f"{last_reason}"
                        )
                        output_fn(
                            "FAIL CLOSED: no new entry until required "
                            "completed-session evidence is available"
                        )
                    else:
                        last_status = "CYCLE_ERROR"
                        output_fn(
                            "AUTONOMOUS CYCLE: ERROR | "
                            f"{type(error).__name__} | {last_reason}"
                        )
                        output_fn(
                            "FAIL CLOSED: reconcile Alpaca state on next iteration"
                        )
                else:
                    last_status = cycle_result.status
                    last_reason = cycle_result.reason
                    output_fn(
                        "AUTONOMOUS CYCLE: "
                        f"{cycle_result.status} | {cycle_result.reason}"
                    )
                    for diagnostic in getattr(cycle_result, "diagnostics", ()):
                        output_fn(f"AUTONOMOUS DIAGNOSTIC: {diagnostic}")
                    execution_proof = getattr(
                        cycle_result,
                        "execution_proof",
                        None,
                    )
                    if execution_proof is not None:
                        output_fn(
                            "ALPACA BROKER ORDER ID: "
                            f"{execution_proof.broker_order_id}"
                        )

                    if (
                        cycle_result.status == "SUBMITTED"
                        or execution_proof is not None
                    ) and entry_cooldown_seconds > 0:
                        entry_cooldown_until = (
                            elapsed_seconds + entry_cooldown_seconds
                        )
                        output_fn(
                            "ENTRY COOLDOWN: STARTED | "
                            f"duration_seconds={entry_cooldown_seconds}"
                        )
        else:
            remaining = max(0, int(next_entry_check_at - elapsed_seconds))
            output_fn(
                "ENTRY DECISION: WAITING | "
                f"next_agent_check_in={remaining} seconds"
            )

        if max_iterations is not None and iterations >= max_iterations:
            return _summary(
                iterations=iterations,
                trade_cycles=trade_cycles,
                last_status=last_status,
                last_reason=last_reason,
            )

        output_fn(next_check_message)
        sleep_fn(risk_check_interval_seconds)
        elapsed_seconds += risk_check_interval_seconds


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run Lockean Lite continuously against the linked Alpaca paper "
            "account while the market is open."
        )
    )
    parser.add_argument(
        "--completed-through",
        required=True,
        type=date.fromisoformat,
        help="Most recent completed market session used for daily evidence.",
    )
    parser.add_argument(
        "--expiration",
        required=True,
        type=date.fromisoformat,
        help="SPY option expiration to trade.",
    )
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=DEFAULT_INTERVAL_SECONDS,
        help="Seconds between fresh AI entry decisions.",
    )
    parser.add_argument(
        "--risk-check-interval-seconds",
        type=int,
        default=DEFAULT_RISK_CHECK_INTERVAL_SECONDS,
        help=(
            "Seconds between portfolio reconciliation and managed-position "
            "exit checks."
        ),
    )
    parser.add_argument(
        "--entry-cooldown-seconds",
        type=int,
        default=DEFAULT_ENTRY_COOLDOWN_SECONDS,
        help=(
            "Minimum seconds after a submitted entry before another fresh "
            "entry decision may run."
        ),
    )
    parser.add_argument(
        "--maximum-open-spreads", type=int, default=DEFAULT_MAXIMUM_OPEN_SPREADS
    )
    parser.add_argument(
        "--maximum-same-structure-units",
        type=int,
        default=DEFAULT_MAXIMUM_SAME_STRUCTURE_UNITS,
        help="Maximum filled units allowed in one exact directional vertical.",
    )
    parser.add_argument(
        "--maximum-allowed-loss", type=Decimal, default=Decimal("150.00")
    )
    parser.add_argument(
        "--maximum-daily-loss",
        type=Decimal,
        default=DEFAULT_MAXIMUM_DAILY_LOSS,
    )
    parser.add_argument(
        "--starting-equity",
        type=Decimal,
        default=COMPETITION_STARTING_EQUITY,
    )
    parser.add_argument(
        "--activity-mode",
        choices=("balanced", "active_paper"),
        default="balanced",
        help=(
            "balanced allows ordinary AI judgment; active_paper intentionally "
            "encourages more paper activity for lifecycle testing."
        ),
    )
    parser.add_argument(
        "--take-profit-percent",
        type=Decimal,
        default=DEFAULT_TAKE_PROFIT_PERCENT,
        help=(
            "Close a managed spread when executable credit implies at least "
            "this percentage return on the entry debit."
        ),
    )
    parser.add_argument(
        "--stop-loss-percent",
        type=Decimal,
        default=DEFAULT_STOP_LOSS_PERCENT,
        help=(
            "Close a managed spread when executable credit implies a loss at "
            "or beyond this percentage of the entry debit."
        ),
    )
    parser.add_argument(
        "--take-profit-price-concession",
        type=Decimal,
        default=DEFAULT_TAKE_PROFIT_PRICE_CONCESSION,
        help=(
            "Maximum cents of close-credit concession used to improve a "
            "take-profit fill, never below the configured take-profit floor."
        ),
    )
    parser.add_argument(
        "--exit-order-timeout-seconds",
        type=int,
        default=DEFAULT_EXIT_ORDER_TIMEOUT_SECONDS,
        help=(
            "Cancel an unfilled exit MLEG after this many seconds so a later "
            "risk cycle can reprice it."
        ),
    )
    parser.add_argument(
        "--entry-order-timeout-seconds",
        type=int,
        default=DEFAULT_ENTRY_ORDER_TIMEOUT_SECONDS,
        help=(
            "Cancel an unfilled entry MLEG after this many seconds. A later "
            "AI cycle must build a fresh proposal and authorization."
        ),
    )
    parser.add_argument(
        "--eod-entry-cutoff-minutes",
        type=int,
        default=DEFAULT_EOD_ENTRY_CUTOFF_MINUTES,
        help=(
            "Stop new entries and cancel pending ENTRY MLEG orders this many "
            "minutes before market close while position risk checks continue."
        ),
    )
    parser.add_argument(
        "--risk-management-only",
        action="store_true",
        help=(
            "Manage and exit existing paper positions while disabling all "
            "new AI entry authority. Pending entry orders are cancelled "
            "before position actions continue."
        ),
    )

    args = parser.parse_args(argv)

    signing_key_text = os.getenv("LOCKEAN_AUTHORIZATION_SIGNING_KEY")
    if not signing_key_text:
        raise ValueError("authorization_signing_key_required")
    signing_key = signing_key_text.encode("utf-8")

    trading_client = create_paper_trading_client_from_environment()
    credentials = load_alpaca_credentials_from_environment()
    option_data_client = OptionHistoricalDataClient(
        credentials.api_key,
        credentials.secret_key,
    )

    def clock_provider():
        return trading_client.get_clock()

    def portfolio_provider():
        return read_live_paper_portfolio_snapshot(
            trading_client=trading_client,
            starting_equity=args.starting_equity,
        )

    def exit_runner(snapshot):
        return run_paper_spread_exit_cycle(
            trading_client=trading_client,
            option_data_client=option_data_client,
            snapshot=snapshot,
            take_profit_percent=args.take_profit_percent,
            stop_loss_percent=args.stop_loss_percent,
            exit_order_timeout_seconds=args.exit_order_timeout_seconds,
            take_profit_price_concession=args.take_profit_price_concession,
        )

    def entry_order_maintenance_runner(snapshot):
        return maintain_pending_entry_orders(
            trading_client=trading_client,
            snapshot=snapshot,
            timeout_seconds=args.entry_order_timeout_seconds,
        )

    def end_of_day_cancel_runner(snapshot):
        return _cancel_pending_entry_mleg_orders(
            trading_client=trading_client,
            snapshot=snapshot,
        )

    def cycle_runner():
        return run_live_production_autonomous_cycle(
            completed_through=args.completed_through,
            expiration=args.expiration,
            maximum_allowed_loss=args.maximum_allowed_loss,
            authorization_signing_key=signing_key,
            agent_activity_mode=args.activity_mode,
            maximum_same_structure_units=args.maximum_same_structure_units,
        )

    print(
        "LOG DAY POLICY: "
        f"TP={args.take_profit_percent}% | "
        f"SL={args.stop_loss_percent}% | "
        f"TP_CONCESSION=${args.take_profit_price_concession} | "
        f"SAME_STRUCTURE_CAP={args.maximum_same_structure_units} | "
        f"ACTIVITY_MODE={args.activity_mode} | "
        f"AI_CADENCE={args.interval_seconds}s | "
        f"RISK_CADENCE={args.risk_check_interval_seconds}s | "
        f"ENTRY_COOLDOWN={args.entry_cooldown_seconds}s | "
        "NEW_ENTRIES="
        f"{'DISABLED' if args.risk_management_only else 'ENABLED'}"
    )

    run_autonomous_paper_session(
        clock_provider=clock_provider,
        portfolio_provider=portfolio_provider,
        cycle_runner=cycle_runner,
        exit_runner=exit_runner,
        entry_order_maintenance_runner=entry_order_maintenance_runner,
        end_of_day_cancel_runner=end_of_day_cancel_runner,
        interval_seconds=args.interval_seconds,
        risk_check_interval_seconds=args.risk_check_interval_seconds,
        entry_cooldown_seconds=args.entry_cooldown_seconds,
        maximum_open_spreads=args.maximum_open_spreads,
        maximum_daily_loss=args.maximum_daily_loss,
        end_of_day_entry_cutoff_minutes=args.eod_entry_cutoff_minutes,
        new_entries_enabled=not args.risk_management_only,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
