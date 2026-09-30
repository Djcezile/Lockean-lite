from datetime import date, datetime, timezone
from io import StringIO

from lockean_lite.session_launcher import (
    build_approved_session_arguments,
    build_session_log_path,
    run_logged_session,
)


def test_build_session_log_path_places_timestamped_log_under_repo_logs(tmp_path):
    path = build_session_log_path(
        repo_root=tmp_path,
        day_number=18,
        now=datetime(2026, 10, 1, 13, 30, 45, tzinfo=timezone.utc),
    )

    assert path == (
        tmp_path / "logs" / "lockean_lite_DAY18_20261001_133045.log"
    )


def test_approved_session_arguments_preserve_the_validated_paper_policy():
    arguments = build_approved_session_arguments(
        completed_through=date(2026, 9, 30),
        expiration=date(2026, 10, 2),
    )

    assert arguments == [
        "--completed-through",
        "2026-09-30",
        "--expiration",
        "2026-10-02",
        "--interval-seconds",
        "300",
        "--risk-check-interval-seconds",
        "30",
        "--entry-cooldown-seconds",
        "600",
        "--maximum-open-spreads",
        "2",
        "--maximum-same-structure-units",
        "1",
        "--maximum-allowed-loss",
        "150",
        "--maximum-daily-loss",
        "300",
        "--take-profit-percent",
        "20",
        "--stop-loss-percent",
        "20",
        "--take-profit-price-concession",
        "0.02",
        "--exit-order-timeout-seconds",
        "240",
        "--entry-order-timeout-seconds",
        "240",
        "--eod-entry-cutoff-minutes",
        "5",
        "--loss-loop-direction-cooldown-seconds",
        "3600",
        "--maximum-session-stop-loss-fills",
        "2",
        "--activity-mode",
        "active_paper",
    ]


def test_run_logged_session_creates_logs_directory_and_tees_console_output(
    tmp_path,
):
    received_arguments = []
    console = StringIO()

    def session_main(arguments):
        received_arguments.extend(arguments)
        print("LOCKEAN TEST SESSION")
        return 0

    exit_code, log_path = run_logged_session(
        repo_root=tmp_path,
        day_number=18,
        completed_through=date(2026, 9, 30),
        expiration=date(2026, 10, 2),
        now=datetime(2026, 10, 1, 13, 30, 45, tzinfo=timezone.utc),
        session_main=session_main,
        console=console,
    )

    assert exit_code == 0
    assert log_path.parent == tmp_path / "logs"
    assert log_path.is_file()
    assert received_arguments == build_approved_session_arguments(
        completed_through=date(2026, 9, 30),
        expiration=date(2026, 10, 2),
    )
    assert "LOCKEAN TEST SESSION" in console.getvalue()
    assert "LOCKEAN TEST SESSION" in log_path.read_text(encoding="utf-8")
