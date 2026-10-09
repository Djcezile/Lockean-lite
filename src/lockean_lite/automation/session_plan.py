"""Read-only, fail-closed plan for a Lockean Lite scheduled paper session."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import re
import sys
import time
from zoneinfo import ZoneInfo


NEW_YORK = ZoneInfo("America/New_York")
LOG_PATTERN = re.compile(
    r"^lockean_lite_DAY([1-9][0-9]*)_[0-9]{8}_[0-9]{6}\.log$"
)
SUCCESS_MARKER = "SESSION RUN RESULT: COMPLETE | exit_code=0"
MARKET_CLOSE_MARKER = "MARKET CLOSED: autonomous session complete"


class PlanError(Exception):
    """A deterministic planning invariant was not satisfied."""


class BrokerUnavailable(Exception):
    """Sanitized read-only broker planning exhaustion."""

    def __init__(self, attempts: int):
        self.attempts = attempts
        super().__init__("broker_or_planner_unavailable")


def completed_days(log_directory: Path) -> set[int]:
    """Return day numbers with both canonical close and success markers."""
    completed: set[int] = set()
    if not log_directory.is_dir():
        raise PlanError("logs_directory_missing")

    for path in log_directory.glob("lockean_lite_DAY*.log"):
        match = LOG_PATTERN.fullmatch(path.name)
        if match is None:
            continue
        found_success = False
        found_close = False
        try:
            with path.open("r", encoding="utf-8", errors="replace") as stream:
                for line in stream:
                    found_success = found_success or SUCCESS_MARKER in line
                    found_close = found_close or MARKET_CLOSE_MARKER in line
        except OSError as error:
            raise PlanError("cannot_read_session_logs") from error
        if found_success and found_close:
            completed.add(int(match.group(1)))
    return completed


def next_day_number(log_directory: Path) -> int:
    days = completed_days(log_directory)
    if not days:
        raise PlanError("no_verified_completed_session")
    return max(days) + 1


def following_friday(day: date) -> date:
    """Return the first Friday strictly after the trading date."""
    offset = (4 - day.weekday()) % 7
    return day + timedelta(days=offset or 7)


def make_plan(
    today: date,
    market_dates: set[date],
    available_expirations: set[date],
    log_directory: Path,
    *,
    market_open: str | None = None,
    market_close: str | None = None,
) -> dict:
    if today not in market_dates:
        return {
            "status": "SKIP",
            "reason": "market_closed",
            "market_date": today.isoformat(),
        }

    previous = sorted(day for day in market_dates if day < today)
    if not previous:
        raise PlanError("previous_market_session_unavailable")

    target = following_friday(today)
    if target not in available_expirations:
        raise PlanError("spy_target_expiration_unverified")

    result = {
        "status": "READY",
        "market_date": today.isoformat(),
    }
    if market_open is not None:
        result["market_open"] = market_open
    if market_close is not None:
        result["market_close"] = market_close
    result.update(
        {
            "day_number": next_day_number(log_directory),
            "completed_through": previous[-1].isoformat(),
            "expiration": target.isoformat(),
            "paper_only": True,
        }
    )
    return result


def _as_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _as_market_datetime(value: datetime, market_date: date) -> datetime:
    if not isinstance(value, datetime):
        value = datetime.fromisoformat(str(value))
    if value.tzinfo is None:
        value = value.replace(tzinfo=NEW_YORK)
    value = value.astimezone(NEW_YORK)
    if value.date() != market_date:
        raise PlanError("broker_calendar_timestamp_invalid")
    return value


def market_session_from_calendar(today: date, calendar) -> dict[str, str]:
    """Normalize an Alpaca calendar response, including broker early closes."""
    item = next(
        (entry for entry in calendar if _as_date(entry.date) == today),
        None,
    )
    if item is None:
        return {"status": "CLOSED", "market_date": today.isoformat()}
    return {
        "status": "OPEN",
        "market_date": today.isoformat(),
        "market_open": _as_market_datetime(item.open, today).isoformat(),
        "market_close": _as_market_datetime(item.close, today).isoformat(),
    }


def broker_market_session(today: date) -> dict[str, str]:
    """Read only the Alpaca PAPER calendar for independent monitoring."""
    from alpaca.trading.requests import GetCalendarRequest
    from lockean_lite.alpaca_client_factory import (
        create_paper_trading_client_from_environment,
    )

    client = create_paper_trading_client_from_environment()
    calendar = client.get_calendar(
        GetCalendarRequest(start=today, end=today)
    )
    return market_session_from_calendar(today, calendar)


def retry_broker_market_session(
    today: date,
    *,
    max_attempts: int = 3,
    delay_seconds: float = 20,
    market_session_runner=None,
    sleep_fn=None,
) -> dict[str, str]:
    if max_attempts < 1 or delay_seconds < 0:
        raise PlanError("invalid_calendar_retry_configuration")
    market_session_runner = market_session_runner or broker_market_session
    sleep_fn = sleep_fn or time.sleep
    for attempt in range(1, max_attempts + 1):
        try:
            return market_session_runner(today)
        except PlanError:
            raise
        except Exception as error:
            if attempt >= max_attempts:
                raise BrokerUnavailable(attempt) from error
            sleep_fn(delay_seconds)
    raise AssertionError("unreachable")


def broker_plan(today: date, log_directory: Path) -> dict:
    """Build a plan using Alpaca PAPER calendar and option reads only."""
    from alpaca.trading.enums import ContractType
    from alpaca.trading.requests import (
        GetCalendarRequest,
        GetOptionContractsRequest,
    )
    from lockean_lite.alpaca_client_factory import (
        create_paper_trading_client_from_environment,
    )

    client = create_paper_trading_client_from_environment()
    calendar = tuple(
        client.get_calendar(
            GetCalendarRequest(start=today - timedelta(days=21), end=today)
        )
    )
    market_dates = {_as_date(item.date) for item in calendar}
    session = market_session_from_calendar(today, calendar)

    if session["status"] == "CLOSED":
        return make_plan(today, market_dates, set(), log_directory)

    target = following_friday(today)
    contracts = client.get_option_contracts(
        GetOptionContractsRequest(
            underlying_symbols=["SPY"],
            expiration_date=target,
            type=ContractType.CALL,
            limit=100,
        )
    )
    available_expirations = {
        _as_date(contract.expiration_date)
        for contract in contracts.option_contracts
        if getattr(contract, "tradable", False)
    }
    return make_plan(
        today,
        market_dates,
        available_expirations,
        log_directory,
        market_open=session["market_open"],
        market_close=session["market_close"],
    )


def retry_broker_plan(
    today: date,
    log_directory: Path,
    *,
    max_attempts: int = 7,
    delay_seconds: float = 30,
    broker_runner=None,
    sleep_fn=None,
) -> dict:
    """Retry only read-only planning; never retry a trading session."""
    if max_attempts < 1 or delay_seconds < 0:
        raise PlanError("invalid_planning_retry_configuration")
    broker_runner = broker_runner or broker_plan
    sleep_fn = sleep_fn or time.sleep

    for attempt in range(1, max_attempts + 1):
        try:
            plan = broker_runner(today, log_directory)
        except PlanError:
            raise
        except Exception as error:
            if attempt >= max_attempts:
                raise BrokerUnavailable(attempt) from error
            sleep_fn(delay_seconds)
            continue
        return {**plan, "planning_attempts": attempt}
    raise AssertionError("unreachable")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=None,
        help="Inspection only; the Windows execution wrapper never sets this.",
    )
    args = parser.parse_args(argv)
    today = args.as_of or datetime.now(NEW_YORK).date()

    try:
        plan = retry_broker_plan(today, args.repo_root / "logs")
    except PlanError as error:
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "reason": str(error),
                    "planning_attempts": 1,
                }
            )
        )
        return 2
    except BrokerUnavailable as error:
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "reason": str(error),
                    "planning_attempts": error.attempts,
                }
            )
        )
        return 3
    except Exception:
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "reason": "broker_or_planner_unavailable",
                }
            )
        )
        return 3

    print(json.dumps(plan, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
