"""Independent evidence monitor for the Windows scheduled paper session."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Callable
from zoneinfo import ZoneInfo

from lockean_lite.automation.notification import (
    AlertEvent,
    build_notification_payload,
    deliver_notification,
)
from lockean_lite.automation.session_plan import retry_broker_market_session


NEW_YORK = ZoneInfo("America/New_York")
HEARTBEAT_PATTERN = re.compile(
    r"^SESSION HEARTBEAT: iteration=[0-9]+ \| observed_at=(\S+)$",
    re.MULTILINE,
)
RUNNER_EXIT_PATTERN = re.compile(r"RUNNER_EXIT_CODE: ([0-9]+)")
COMPLETE_MARKER = "SESSION RUN RESULT: COMPLETE | exit_code=0"
CLOSE_MARKER = "MARKET CLOSED: autonomous session complete"
UNEXPECTED_TERMINALS = (
    "SESSION RUN RESULT: ABORTED",
    "SESSION RUN RESULT: FAILED",
    "SESSION RUN RESULT: INTERRUPTED",
    "SESSION RUN RESULT: BLOCKED",
)


@dataclass(frozen=True)
class SessionEvidence:
    started: bool = False
    scheduler_audit: str = ""
    session_log: str | None = None
    completed_record: bool = False


def _deduplicate(events: list[AlertEvent]) -> tuple[AlertEvent, ...]:
    result = []
    seen = set()
    for event in events:
        if event.code not in seen:
            result.append(event)
            seen.add(event.code)
    return tuple(result)


def _latest_heartbeat(text: str) -> datetime | None:
    matches = HEARTBEAT_PATTERN.findall(text)
    if not matches:
        return None
    try:
        observed = datetime.fromisoformat(matches[-1])
    except ValueError:
        return None
    if observed.tzinfo is None:
        return None
    return observed


def evaluate_session_health(
    *,
    now: datetime,
    market_date: date,
    market_open: datetime,
    market_close: datetime,
    evidence: SessionEvidence,
    heartbeat_timeout: timedelta,
    completion_grace: timedelta,
) -> tuple[AlertEvent, ...]:
    """Classify only lifecycle evidence; never inspect balances or positions."""
    if now.tzinfo is None or market_open.tzinfo is None or market_close.tzinfo is None:
        raise ValueError("watchdog_datetimes_must_be_timezone_aware")
    if now.astimezone(NEW_YORK).date() != market_date:
        raise ValueError("watchdog_market_date_mismatch")

    events: list[AlertEvent] = []
    audit = evidence.scheduler_audit
    session_log = evidence.session_log
    complete = bool(
        session_log
        and CLOSE_MARKER in session_log
        and COMPLETE_MARKER in session_log
    )

    if "PLANNER FAILURE:" in audit:
        events.append(
            AlertEvent("planner_failure", "Read-only broker planning failed.")
        )
    if "BLOCKED:" in audit:
        events.append(
            AlertEvent("startup_blocked", "Scheduled session startup was blocked.")
        )
    if "SOURCE REVISION BLOCKED" in audit or "WATCHDOG SOURCE MISMATCH" in audit:
        events.append(
            AlertEvent(
                "source_revision_mismatch",
                "Approved and available source revisions do not match.",
            )
        )

    runner_codes = [int(value) for value in RUNNER_EXIT_PATTERN.findall(audit)]
    if any(value != 0 for value in runner_codes):
        events.append(
            AlertEvent("runner_nonzero", "Paper session runner returned nonzero.")
        )

    if session_log and any(marker in session_log for marker in UNEXPECTED_TERMINALS):
        events.append(
            AlertEvent(
                "unexpected_terminal",
                "Paper session ended with an unexpected terminal state.",
            )
        )

    launch_deadline = market_open - timedelta(minutes=5)
    if now >= launch_deadline and not evidence.started:
        events.append(
            AlertEvent("task_not_started", "Daily paper task did not start on time.")
        )
    elif evidence.started and now >= market_open and session_log is None:
        events.append(
            AlertEvent("session_log_missing", "Started task has no canonical session log.")
        )

    monitoring_end = market_close + completion_grace
    has_terminal = bool(
        session_log
        and (
            complete
            or any(marker in session_log for marker in UNEXPECTED_TERMINALS)
        )
    )
    if (
        evidence.started
        and session_log is not None
        and market_open <= now <= monitoring_end
        and not has_terminal
    ):
        heartbeat = _latest_heartbeat(session_log)
        if heartbeat is None:
            events.append(
                AlertEvent("heartbeat_missing", "Session log has no valid heartbeat.")
            )
        elif now.astimezone(heartbeat.tzinfo) - heartbeat > heartbeat_timeout:
            events.append(
                AlertEvent("heartbeat_stale", "Session heartbeat stopped advancing.")
            )

    if now >= monitoring_end and (not complete or not evidence.completed_record):
        code = (
            "completion_record_missing"
            if complete and not evidence.completed_record
            else "session_incomplete_after_close"
        )
        message = (
            "Canonical session completed but its scheduler receipt is missing."
            if code == "completion_record_missing"
            else "Session has no reconciled successful completion after market close."
        )
        events.append(AlertEvent(code, message))

    return _deduplicate(events)


def _read_optional(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except (FileNotFoundError, OSError):
        return ""


def discover_session_evidence(
    *,
    repo_root: Path,
    automation_root: Path,
    market_date: date,
) -> SessionEvidence:
    date_iso = market_date.isoformat()
    date_compact = market_date.strftime("%Y%m%d")
    state_root = automation_root / "state"
    start_paths = (
        state_root / f"started_{date_iso}.json",
        automation_root / "logs" / f"started_{date_iso}.txt",
    )
    completed_path = state_root / f"completed_{date_iso}.json"
    audit_path = automation_root / "logs" / f"scheduler_{date_compact}.log"
    candidates = sorted(
        (repo_root / "logs").glob(
            f"lockean_lite_DAY*_{date_compact}_*.log"
        )
    )
    session_log = _read_optional(candidates[-1]) if candidates else None
    return SessionEvidence(
        started=any(path.is_file() for path in start_paths),
        scheduler_audit=_read_optional(audit_path),
        session_log=session_log,
        completed_record=completed_path.is_file(),
    )


class AlertLedger:
    def __init__(self, path: Path):
        self.path = Path(path)

    def _load(self) -> dict[str, list[str]]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return {}
        if not isinstance(value, dict):
            return {}
        return {
            str(key): [str(item) for item in items]
            for key, items in value.items()
            if isinstance(items, list)
        }

    def delivered(self, market_date: date, code: str) -> bool:
        return code in self._load().get(market_date.isoformat(), [])

    def record(self, market_date: date, code: str) -> None:
        data = self._load()
        date_key = market_date.isoformat()
        codes = set(data.get(date_key, []))
        codes.add(code)
        data[date_key] = sorted(codes)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)


def dispatch_new_alerts(
    events: tuple[AlertEvent, ...],
    *,
    market_date: date,
    ledger: AlertLedger,
    sender: Callable[[AlertEvent, date], None],
) -> tuple[str, ...]:
    delivered = []
    for event in events:
        if ledger.delivered(market_date, event.code):
            continue
        sender(event, market_date)
        ledger.record(market_date, event.code)
        delivered.append(event.code)
    return tuple(delivered)


def _append_audit(path: Path, message: str, now: datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(f"{now.isoformat()} {message}\n")


def _simulation(event_code: str) -> int:
    event = AlertEvent(event_code, "Simulated watchdog notification.")
    payload = build_notification_payload(
        event,
        market_date=datetime.now(NEW_YORK).date().isoformat(),
    )
    print("SIMULATED NOTIFICATION: " + json.dumps(payload, sort_keys=True))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--automation-root", type=Path, required=True)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=120)
    parser.add_argument("--heartbeat-timeout-seconds", type=int, default=180)
    parser.add_argument("--completion-grace-minutes", type=int, default=15)
    parser.add_argument("--simulate-event", default=None)
    args = parser.parse_args(argv)

    if args.simulate_event:
        return _simulation(args.simulate_event)
    if args.poll_seconds < 30 or args.heartbeat_timeout_seconds < 60:
        print("WATCHDOG BLOCKED: invalid_monitor_configuration")
        return 2

    now = datetime.now(NEW_YORK)
    market_date = now.date()
    audit_path = (
        args.automation_root
        / "logs"
        / f"watchdog_{market_date.strftime('%Y%m%d')}.log"
    )

    try:
        market_session = retry_broker_market_session(market_date)
    except Exception:
        _append_audit(audit_path, "WATCHDOG BLOCKED: calendar_unavailable", now)
        webhook_url = os.environ.get(
            "LOCKEAN_NOTIFICATION_WEBHOOK",
            "",
        ).strip()
        if webhook_url:
            try:
                deliver_notification(
                    webhook_url,
                    build_notification_payload(
                        AlertEvent(
                            "watchdog_calendar_unavailable",
                            "Independent market-calendar check failed.",
                        ),
                        market_date=market_date.isoformat(),
                    ),
                )
            except Exception:
                _append_audit(
                    audit_path,
                    "ALERT DELIVERY FAILED",
                    now,
                )
        print("WATCHDOG BLOCKED: calendar_unavailable")
        return 3

    if market_session["status"] == "CLOSED":
        _append_audit(audit_path, "WATCHDOG SKIP: market_closed", now)
        return 0

    market_open = datetime.fromisoformat(market_session["market_open"])
    market_close = datetime.fromisoformat(market_session["market_close"])
    completion_grace = timedelta(minutes=args.completion_grace_minutes)
    ledger = AlertLedger(args.automation_root / "state" / "alert-ledger.json")
    webhook_url = os.environ.get("LOCKEAN_NOTIFICATION_WEBHOOK", "").strip()

    def sender(event: AlertEvent, event_date: date) -> None:
        if not webhook_url:
            raise RuntimeError("notification_destination_unavailable")
        deliver_notification(
            webhook_url,
            build_notification_payload(
                event,
                market_date=event_date.isoformat(),
            ),
        )

    while True:
        now = datetime.now(NEW_YORK)
        evidence = discover_session_evidence(
            repo_root=args.repo_root,
            automation_root=args.automation_root,
            market_date=market_date,
        )
        events = evaluate_session_health(
            now=now,
            market_date=market_date,
            market_open=market_open,
            market_close=market_close,
            evidence=evidence,
            heartbeat_timeout=timedelta(
                seconds=args.heartbeat_timeout_seconds
            ),
            completion_grace=completion_grace,
        )
        for event in events:
            _append_audit(audit_path, f"ALERT DETECTED: {event.code}", now)
        try:
            delivered = dispatch_new_alerts(
                events,
                market_date=market_date,
                ledger=ledger,
                sender=sender,
            )
        except Exception:
            _append_audit(audit_path, "ALERT DELIVERY FAILED", now)
        else:
            for code in delivered:
                _append_audit(audit_path, f"ALERT DELIVERED: {code}", now)

        if args.once or now >= market_close + completion_grace:
            return 0
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    sys.exit(main())
