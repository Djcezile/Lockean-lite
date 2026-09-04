import argparse
import os
import time
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from lockean_lite.alpaca_client_factory import (
    create_paper_trading_client_from_environment,
)
from lockean_lite.paper_portfolio_snapshot import (
    COMPETITION_STARTING_EQUITY,
    read_live_paper_portfolio_snapshot,
    render_paper_portfolio_snapshot,
)
from lockean_lite.portfolio_gate import (
    evaluate_portfolio_entry,
)
from lockean_lite.production_runtime import (
    run_live_production_autonomous_cycle,
)


DEFAULT_INTERVAL_SECONDS = 300
DEFAULT_MAXIMUM_OPEN_SPREADS = 5
DEFAULT_MAXIMUM_DAILY_LOSS = Decimal("750.00")


@dataclass(frozen=True)
class AutonomousSessionSummary:
    iterations: int
    trade_cycles: int
    last_status: str
    last_reason: str


def run_autonomous_paper_session(
    *,
    clock_provider,
    portfolio_provider,
    cycle_runner,
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    maximum_open_spreads: int = DEFAULT_MAXIMUM_OPEN_SPREADS,
    maximum_daily_loss: Decimal = DEFAULT_MAXIMUM_DAILY_LOSS,
    sleep_fn=time.sleep,
    output_fn=print,
    max_iterations: int | None = None,
) -> AutonomousSessionSummary:
    if interval_seconds <= 0:
        raise ValueError(
            "interval_seconds_must_be_positive"
        )

    iterations = 0
    trade_cycles = 0
    last_status = "WAITING"
    last_reason = "session_not_started"
    market_has_opened = False

    output_fn(
        "LOCKEAN AUTONOMOUS PAPER SESSION"
    )
    output_fn(
        "==============================="
    )
    output_fn(
        "MODE: ALPACA PAPER ONLY"
    )
    output_fn(
        (
            "MAX MANAGED SPREAD UNITS: "
            f"{maximum_open_spreads}"
        )
    )
    output_fn(
        (
            "DAILY LOSS HALT: -$"
            f"{maximum_daily_loss:.2f}"
        )
    )

    while True:
        iterations += 1

        try:
            clock = clock_provider()
            snapshot = portfolio_provider()
        except Exception as error:
            last_status = "STATE_UNAVAILABLE"
            last_reason = "alpaca_session_state_unavailable"
            output_fn("")
            output_fn(
                (
                    "ALPACA SESSION STATE: UNAVAILABLE | "
                    f"{type(error).__name__}"
                )
            )
            output_fn(
                "FAIL CLOSED: no autonomous order attempt"
            )

            if (
                max_iterations is not None
                and iterations >= max_iterations
            ):
                return AutonomousSessionSummary(
                    iterations=iterations,
                    trade_cycles=trade_cycles,
                    last_status=last_status,
                    last_reason=last_reason,
                )

            sleep_fn(
                min(interval_seconds, 60)
            )
            continue

        output_fn("")
        output_fn(
            render_paper_portfolio_snapshot(
                snapshot
            )
        )
        output_fn("")
        output_fn(
            (
                "ALPACA MARKET CLOCK: "
                f"{'OPEN' if clock.is_open else 'CLOSED'}"
            )
        )

        if not clock.is_open:
            if market_has_opened:
                last_status = "SESSION_COMPLETE"
                last_reason = "market_closed"
                output_fn(
                    "MARKET CLOSED: autonomous session complete"
                )
                return AutonomousSessionSummary(
                    iterations=iterations,
                    trade_cycles=trade_cycles,
                    last_status=last_status,
                    last_reason=last_reason,
                )

            last_status = "WAITING"
            last_reason = "market_closed_waiting_for_open"
            output_fn(
                (
                    "NEXT MARKET OPEN: "
                    f"{clock.next_open}"
                )
            )

            if (
                max_iterations is not None
                and iterations >= max_iterations
            ):
                return AutonomousSessionSummary(
                    iterations=iterations,
                    trade_cycles=trade_cycles,
                    last_status=last_status,
                    last_reason=last_reason,
                )

            sleep_fn(
                min(interval_seconds, 60)
            )
            continue

        market_has_opened = True

        entry_decision = evaluate_portfolio_entry(
            snapshot=snapshot,
            maximum_open_spreads=(
                maximum_open_spreads
            ),
            maximum_daily_loss=(
                maximum_daily_loss
            ),
        )

        if not entry_decision.allowed:
            last_status = "ENTRY_BLOCKED"
            last_reason = entry_decision.reason
            output_fn(
                (
                    "PORTFOLIO ENTRY GATE: BLOCKED | "
                    f"{entry_decision.reason}"
                )
            )
        else:
            trade_cycles += 1

            try:
                cycle_result = cycle_runner()
            except Exception as error:
                last_status = "CYCLE_ERROR"
                last_reason = "autonomous_cycle_failed_closed"
                output_fn(
                    (
                        "AUTONOMOUS CYCLE: ERROR | "
                        f"{type(error).__name__}"
                    )
                )
                output_fn(
                    "FAIL CLOSED: reconcile Alpaca state on next iteration"
                )
            else:
                last_status = cycle_result.status
                last_reason = cycle_result.reason
                output_fn(
                    (
                        "AUTONOMOUS CYCLE: "
                        f"{cycle_result.status} | "
                        f"{cycle_result.reason}"
                    )
                )

                execution_proof = getattr(
                    cycle_result,
                    "execution_proof",
                    None,
                )
                if execution_proof is not None:
                    output_fn(
                        (
                            "ALPACA BROKER ORDER ID: "
                            f"{execution_proof.broker_order_id}"
                        )
                    )

        if (
            max_iterations is not None
            and iterations >= max_iterations
        ):
            return AutonomousSessionSummary(
                iterations=iterations,
                trade_cycles=trade_cycles,
                last_status=last_status,
                last_reason=last_reason,
            )

        output_fn(
            (
                "NEXT AUTONOMOUS CHECK IN "
                f"{interval_seconds} SECONDS"
            )
        )
        sleep_fn(interval_seconds)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run Lockean Lite continuously against "
            "the linked Alpaca paper account while "
            "the market is open."
        )
    )

    parser.add_argument(
        "--completed-through",
        required=True,
        type=date.fromisoformat,
        help=(
            "Most recent completed market session "
            "used for daily evidence."
        ),
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
    )
    parser.add_argument(
        "--maximum-open-spreads",
        type=int,
        default=DEFAULT_MAXIMUM_OPEN_SPREADS,
    )
    parser.add_argument(
        "--maximum-allowed-loss",
        type=Decimal,
        default=Decimal("150.00"),
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

    args = parser.parse_args(argv)

    signing_key_text = os.getenv(
        "LOCKEAN_AUTHORIZATION_SIGNING_KEY"
    )
    if not signing_key_text:
        raise ValueError(
            "authorization_signing_key_required"
        )

    signing_key = signing_key_text.encode(
        "utf-8"
    )

    trading_client = (
        create_paper_trading_client_from_environment()
    )

    def clock_provider():
        return trading_client.get_clock()

    def portfolio_provider():
        return read_live_paper_portfolio_snapshot(
            trading_client=trading_client,
            starting_equity=args.starting_equity,
        )

    def cycle_runner():
        return run_live_production_autonomous_cycle(
            completed_through=(
                args.completed_through
            ),
            expiration=args.expiration,
            maximum_allowed_loss=(
                args.maximum_allowed_loss
            ),
            authorization_signing_key=(
                signing_key
            ),
        )

    run_autonomous_paper_session(
        clock_provider=clock_provider,
        portfolio_provider=portfolio_provider,
        cycle_runner=cycle_runner,
        interval_seconds=args.interval_seconds,
        maximum_open_spreads=(
            args.maximum_open_spreads
        ),
        maximum_daily_loss=(
            args.maximum_daily_loss
        ),
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
