from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from lockean_lite.automation.notification import AlertEvent
from lockean_lite.automation.session_watchdog import (
    AlertLedger,
    SessionEvidence,
    dispatch_new_alerts,
    evaluate_session_health,
)


EASTERN = ZoneInfo("America/New_York")
MARKET_DATE = date(2026, 10, 12)
MARKET_OPEN = datetime(2026, 10, 12, 9, 30, tzinfo=EASTERN)
MARKET_CLOSE = datetime(2026, 10, 12, 16, 0, tzinfo=EASTERN)


def _evaluate(*, now, evidence, timeout_seconds=180):
    return evaluate_session_health(
        now=now,
        market_date=MARKET_DATE,
        market_open=MARKET_OPEN,
        market_close=MARKET_CLOSE,
        evidence=evidence,
        heartbeat_timeout=timedelta(seconds=timeout_seconds),
        completion_grace=timedelta(minutes=15),
    )


def test_watchdog_alerts_when_task_never_starts():
    alerts = _evaluate(
        now=datetime(2026, 10, 12, 9, 26, tzinfo=EASTERN),
        evidence=SessionEvidence(),
    )
    assert [alert.code for alert in alerts] == ["task_not_started"]


def test_watchdog_classifies_planner_and_startup_failures():
    alerts = _evaluate(
        now=datetime(2026, 10, 12, 9, 26, tzinfo=EASTERN),
        evidence=SessionEvidence(
            scheduler_audit=(
                "PLANNER FAILURE: reason=broker_or_planner_unavailable\n"
                "BLOCKED: broker_planning | inspect local logs\n"
            ),
        ),
    )
    assert {alert.code for alert in alerts} == {
        "planner_failure",
        "startup_blocked",
        "task_not_started",
    }


def test_watchdog_detects_stale_heartbeat_without_parsing_account_values():
    evidence = SessionEvidence(
        started=True,
        session_log=(
            "SESSION HEARTBEAT: iteration=1 | "
            "observed_at=2026-10-12T13:30:00+00:00\n"
        ),
    )

    alerts = _evaluate(
        now=datetime(2026, 10, 12, 9, 34, tzinfo=EASTERN),
        evidence=evidence,
    )
    assert [alert.code for alert in alerts] == ["heartbeat_stale"]


def test_watchdog_reports_nonzero_runner_and_unexpected_terminal():
    evidence = SessionEvidence(
        started=True,
        scheduler_audit="RUNNER_EXIT_CODE: 1\n",
        session_log="SESSION RUN RESULT: ABORTED | RuntimeError | unexpected_error\n",
    )

    alerts = _evaluate(
        now=datetime(2026, 10, 12, 11, 0, tzinfo=EASTERN),
        evidence=evidence,
    )
    assert {alert.code for alert in alerts} == {
        "runner_nonzero",
        "unexpected_terminal",
    }


def test_watchdog_alerts_on_source_revision_mismatch():
    alerts = _evaluate(
        now=datetime(2026, 10, 12, 9, 26, tzinfo=EASTERN),
        evidence=SessionEvidence(
            started=True,
            scheduler_audit="WATCHDOG SOURCE MISMATCH\n",
            session_log=(
                "SESSION HEARTBEAT: iteration=1 | "
                "observed_at=2026-10-12T13:25:30+00:00\n"
            ),
        ),
    )
    assert [alert.code for alert in alerts] == [
        "source_revision_mismatch"
    ]


def test_watchdog_requires_canonical_completion_record_after_early_close():
    early_close = datetime(2026, 11, 27, 13, 0, tzinfo=EASTERN)
    alerts = evaluate_session_health(
        now=datetime(2026, 11, 27, 13, 16, tzinfo=EASTERN),
        market_date=date(2026, 11, 27),
        market_open=datetime(2026, 11, 27, 9, 30, tzinfo=EASTERN),
        market_close=early_close,
        evidence=SessionEvidence(
            started=True,
            session_log=(
                "MARKET CLOSED: autonomous session complete\n"
                "SESSION RUN RESULT: COMPLETE | exit_code=0\n"
            ),
            completed_record=False,
        ),
        heartbeat_timeout=timedelta(minutes=3),
        completion_grace=timedelta(minutes=15),
    )

    assert [alert.code for alert in alerts] == ["completion_record_missing"]


def test_watchdog_is_quiet_for_complete_reconciled_session():
    alerts = _evaluate(
        now=datetime(2026, 10, 12, 16, 16, tzinfo=EASTERN),
        evidence=SessionEvidence(
            started=True,
            scheduler_audit="RUNNER_EXIT_CODE: 0\n",
            session_log=(
                "MARKET CLOSED: autonomous session complete\n"
                "SESSION RUN RESULT: COMPLETE | exit_code=0\n"
            ),
            completed_record=True,
        ),
    )
    assert alerts == ()


def test_alert_delivery_is_idempotent_and_failed_delivery_is_retried(tmp_path):
    ledger = AlertLedger(tmp_path / "alert-ledger.json")
    alert = AlertEvent("heartbeat_stale", "Heartbeat stopped.")
    calls = []

    dispatch_new_alerts(
        (alert,),
        market_date=MARKET_DATE,
        ledger=ledger,
        sender=lambda event, market_date: calls.append((event.code, market_date)),
    )
    dispatch_new_alerts(
        (alert,),
        market_date=MARKET_DATE,
        ledger=ledger,
        sender=lambda event, market_date: calls.append((event.code, market_date)),
    )

    assert calls == [("heartbeat_stale", MARKET_DATE)]

    failed = AlertEvent("runner_nonzero", "Runner failed.")

    def fail(_event, _market_date):
        raise RuntimeError("delivery unavailable")

    try:
        dispatch_new_alerts(
            (failed,),
            market_date=MARKET_DATE,
            ledger=ledger,
            sender=fail,
        )
    except RuntimeError:
        pass

    retry_calls = []
    dispatch_new_alerts(
        (failed,),
        market_date=MARKET_DATE,
        ledger=ledger,
        sender=lambda event, _: retry_calls.append(event.code),
    )
    assert retry_calls == ["runner_nonzero"]
