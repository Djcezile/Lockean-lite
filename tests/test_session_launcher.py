from datetime import date, datetime, timezone
from io import StringIO

from lockean_lite.session_launcher import (
    SourceState,
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
        "900",
        "--risk-check-interval-seconds",
        "30",
        "--entry-cooldown-seconds",
        "1800",
        "--maximum-open-spreads",
        "1",
        "--maximum-same-structure-units",
        "1",
        "--maximum-allowed-loss",
        "150",
        "--maximum-daily-loss",
        "150",
        "--take-profit-percent",
        "30",
        "--stop-loss-percent",
        "20",
        "--take-profit-price-concession",
        "0.02",
        "--exit-order-timeout-seconds",
        "240",
        "--entry-order-timeout-seconds",
        "240",
        "--eod-entry-cutoff-minutes",
        "30",
        "--loss-loop-direction-cooldown-seconds",
        "3600",
        "--maximum-session-stop-loss-fills",
        "1",
        "--activity-mode",
        "profit_first",
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
        source_state_provider=lambda _: SourceState(
            git_commit="a" * 40,
            worktree="clean",
        ),
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
    assert "SESSION RUN STARTED AT: 2026-10-01T13:30:45+00:00" in (
        log_path.read_text(encoding="utf-8")
    )
    assert "SESSION RUN RESULT: COMPLETE | exit_code=0" in (
        log_path.read_text(encoding="utf-8")
    )
    assert (
        "SESSION SOURCE: git_commit=" + ("a" * 40) + " | worktree=clean"
        in log_path.read_text(encoding="utf-8")
    )


def test_run_logged_session_records_sanitized_fatal_error(tmp_path):
    console = StringIO()

    def failing_session_main(arguments):
        raise RuntimeError("credential-value-must-not-appear")

    exit_code, log_path = run_logged_session(
        repo_root=tmp_path,
        day_number=20,
        completed_through=date(2026, 10, 2),
        expiration=date(2026, 10, 9),
        now=datetime(2026, 10, 5, 19, 26, 2, tzinfo=timezone.utc),
        session_main=failing_session_main,
        console=console,
        source_state_provider=lambda _: SourceState(
            git_commit="b" * 40,
            worktree="clean",
        ),
    )

    log_text = log_path.read_text(encoding="utf-8")

    assert exit_code == 1
    assert (
        "SESSION RUN RESULT: ABORTED | RuntimeError | unexpected_error"
        in log_text
    )
    assert "credential-value-must-not-appear" not in log_text
    assert "SESSION RUN RESULT: ABORTED" in console.getvalue()


def test_approved_commit_blocks_mismatched_source_before_session_runs(tmp_path):
    calls = []
    console = StringIO()

    exit_code, log_path = run_logged_session(
        repo_root=tmp_path,
        day_number=24,
        completed_through=date(2026, 10, 9),
        expiration=date(2026, 10, 16),
        now=datetime(2026, 10, 12, 13, 15, tzinfo=timezone.utc),
        session_main=lambda arguments: calls.append(arguments),
        console=console,
        approved_commit="c" * 40,
        source_state_provider=lambda _: SourceState(
            git_commit="d" * 40,
            worktree="clean",
        ),
    )

    assert exit_code == 2
    assert calls == []
    assert (
        "SESSION RUN RESULT: BLOCKED | reason=source_revision_unapproved"
        in log_path.read_text(encoding="utf-8")
    )


def test_approved_commit_blocks_tracked_worktree_changes(tmp_path):
    calls = []

    exit_code, _ = run_logged_session(
        repo_root=tmp_path,
        day_number=24,
        completed_through=date(2026, 10, 9),
        expiration=date(2026, 10, 16),
        now=datetime(2026, 10, 12, 13, 15, tzinfo=timezone.utc),
        session_main=lambda arguments: calls.append(arguments),
        approved_commit="e" * 40,
        source_state_provider=lambda _: SourceState(
            git_commit="e" * 40,
            worktree="dirty",
        ),
    )

    assert exit_code == 2
    assert calls == []
