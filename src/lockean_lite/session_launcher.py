import argparse
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, datetime
from pathlib import Path
import sys
from typing import Callable, TextIO

from lockean_lite import autonomous_session


class _TeeTextIO:
    def __init__(self, *streams: TextIO):
        self._streams = streams

    def write(self, text: str) -> int:
        for stream in self._streams:
            stream.write(text)
        return len(text)

    def flush(self) -> None:
        for stream in self._streams:
            stream.flush()


def build_session_log_path(
    *,
    repo_root: Path,
    day_number: int,
    now: datetime,
) -> Path:
    if day_number <= 0:
        raise ValueError("day_number_must_be_positive")

    timestamp = now.strftime("%Y%m%d_%H%M%S")
    return (
        Path(repo_root)
        / "logs"
        / f"lockean_lite_DAY{day_number}_{timestamp}.log"
    )


def build_approved_session_arguments(
    *,
    completed_through: date,
    expiration: date,
) -> list[str]:
    return [
        "--completed-through",
        completed_through.isoformat(),
        "--expiration",
        expiration.isoformat(),
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


def run_logged_session(
    *,
    repo_root: Path,
    day_number: int,
    completed_through: date,
    expiration: date,
    now: datetime,
    session_main: Callable[[list[str]], int] = autonomous_session.main,
    console: TextIO | None = None,
) -> tuple[int, Path]:
    if console is None:
        console = sys.stdout

    log_path = build_session_log_path(
        repo_root=repo_root,
        day_number=day_number,
        now=now,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    arguments = build_approved_session_arguments(
        completed_through=completed_through,
        expiration=expiration,
    )

    with log_path.open("w", encoding="utf-8", buffering=1) as log_file:
        tee = _TeeTextIO(console, log_file)
        print(f"SESSION LOG FILE: {log_path}", file=tee)
        with redirect_stdout(tee), redirect_stderr(tee):
            exit_code = session_main(arguments)

    return exit_code, log_path


def _positive_day_number(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("day number must be positive")
    return number


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the approved Lockean Lite paper session and store a complete "
            "terminal log under the repository logs directory."
        )
    )
    parser.add_argument("--day-number", required=True, type=_positive_day_number)
    parser.add_argument(
        "--completed-through",
        required=True,
        type=date.fromisoformat,
    )
    parser.add_argument(
        "--expiration",
        required=True,
        type=date.fromisoformat,
    )
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[2]
    exit_code, _ = run_logged_session(
        repo_root=repo_root,
        day_number=args.day_number,
        completed_through=args.completed_through,
        expiration=args.expiration,
        now=datetime.now(),
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
