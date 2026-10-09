from datetime import date

import pytest

from lockean_lite.automation.session_plan import (
    BrokerUnavailable,
    PlanError,
    completed_days,
    following_friday,
    make_plan,
    market_session_from_calendar,
    next_day_number,
    retry_broker_plan,
)


def _add_log(directory, day, *, closed=True, complete=True, stamp="20261006"):
    text = "SESSION RUN PARAMETERS: day=x\n"
    if closed:
        text += "MARKET CLOSED: autonomous session complete\n"
    if complete:
        text += "SESSION RUN RESULT: COMPLETE | exit_code=0\n"
    else:
        text += "SESSION RUN RESULT: ABORTED | exception\n"
    (directory / f"lockean_lite_DAY{day}_{stamp}_090000.log").write_text(
        text,
        encoding="utf-8",
    )


def test_completed_days_requires_close_and_success_and_exact_filename(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    _add_log(logs, 21)
    _add_log(logs, 22, closed=False, stamp="20261007")
    _add_log(logs, 23, complete=False, stamp="20261008")
    (logs / "lockean_lite_DAY99_20261009_090000(1).log").write_text(
        "MARKET CLOSED: autonomous session complete\n"
        "SESSION RUN RESULT: COMPLETE | exit_code=0\n",
        encoding="utf-8",
    )

    assert completed_days(logs) == {21}
    assert next_day_number(logs) == 22


def test_friday_expiration_is_strictly_future():
    assert following_friday(date(2026, 10, 8)) == date(2026, 10, 9)
    assert following_friday(date(2026, 10, 9)) == date(2026, 10, 16)


def test_make_plan_uses_previous_market_date_and_verified_expiration(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    _add_log(logs, 23, stamp="20261009")

    plan = make_plan(
        date(2026, 10, 12),
        {date(2026, 10, 9), date(2026, 10, 12)},
        {date(2026, 10, 16)},
        logs,
        market_open="2026-10-12T09:30:00-04:00",
        market_close="2026-10-12T16:00:00-04:00",
    )

    assert plan == {
        "status": "READY",
        "market_date": "2026-10-12",
        "market_open": "2026-10-12T09:30:00-04:00",
        "market_close": "2026-10-12T16:00:00-04:00",
        "day_number": 24,
        "completed_through": "2026-10-09",
        "expiration": "2026-10-16",
        "paper_only": True,
    }


def test_make_plan_skips_non_market_day_without_needing_logs(tmp_path):
    logs = tmp_path / "missing"
    assert make_plan(date(2026, 12, 25), set(), set(), logs) == {
        "status": "SKIP",
        "reason": "market_closed",
        "market_date": "2026-12-25",
    }


def test_make_plan_fails_closed_for_unverified_contract(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    _add_log(logs, 23)

    with pytest.raises(PlanError, match="spy_target_expiration_unverified"):
        make_plan(
            date(2026, 10, 12),
            {date(2026, 10, 9), date(2026, 10, 12)},
            set(),
            logs,
        )


def test_read_only_broker_planning_retries_are_bounded_and_sanitized(tmp_path):
    calls = []
    sleeps = []

    def runner(today, logs):
        calls.append((today, logs))
        raise RuntimeError("secret broker response")

    with pytest.raises(BrokerUnavailable, match="broker_or_planner_unavailable") as error:
        retry_broker_plan(
            date(2026, 10, 12),
            tmp_path,
            max_attempts=3,
            delay_seconds=2,
            broker_runner=runner,
            sleep_fn=sleeps.append,
        )

    assert error.value.attempts == 3
    assert "secret" not in str(error.value)
    assert len(calls) == 3
    assert sleeps == [2, 2]


def test_read_only_broker_planning_can_recover_without_retrying_session(tmp_path):
    calls = []
    sleeps = []

    def runner(today, logs):
        calls.append((today, logs))
        if len(calls) < 3:
            raise ConnectionError("temporary startup network failure")
        return {"status": "READY", "paper_only": True, "day_number": 24}

    result = retry_broker_plan(
        date(2026, 10, 12),
        tmp_path,
        max_attempts=7,
        delay_seconds=30,
        broker_runner=runner,
        sleep_fn=sleeps.append,
    )

    assert result["planning_attempts"] == 3
    assert result["day_number"] == 24
    assert sleeps == [30, 30]


def test_deterministic_plan_error_is_never_retried(tmp_path):
    calls = []

    def runner(today, logs):
        calls.append(today)
        raise PlanError("no_verified_completed_session")

    with pytest.raises(PlanError, match="no_verified_completed_session"):
        retry_broker_plan(
            date(2026, 10, 12),
            tmp_path,
            broker_runner=runner,
            sleep_fn=lambda _: None,
        )

    assert calls == [date(2026, 10, 12)]


def test_market_session_preserves_broker_early_close():
    from datetime import datetime
    from types import SimpleNamespace
    from zoneinfo import ZoneInfo

    eastern = ZoneInfo("America/New_York")
    session = market_session_from_calendar(
        date(2026, 11, 27),
        (
            SimpleNamespace(
                date=date(2026, 11, 27),
                open=datetime(2026, 11, 27, 9, 30, tzinfo=eastern),
                close=datetime(2026, 11, 27, 13, 0, tzinfo=eastern),
            ),
        ),
    )

    assert session == {
        "status": "OPEN",
        "market_date": "2026-11-27",
        "market_open": "2026-11-27T09:30:00-05:00",
        "market_close": "2026-11-27T13:00:00-05:00",
    }


def test_market_session_classifies_holiday_without_guessing_hours():
    assert market_session_from_calendar(date(2026, 12, 25), ()) == {
        "status": "CLOSED",
        "market_date": "2026-12-25",
    }
