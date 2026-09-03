import argparse
from datetime import date, datetime, timezone
from pathlib import Path

from alpaca.data.historical import (
    StockHistoricalDataClient,
)

from lockean_lite.alpaca_credentials import (
    load_alpaca_credentials_from_environment,
)
from lockean_lite.market_evidence_demo import (
    run_market_evidence_demo,
)
from lockean_lite.vix_history_source import (
    fetch_official_vix_history,
)
from lockean_lite.visual_market_evidence_demo import (
    run_visual_market_evidence_demo,
)

DEFAULT_HISTORY_START = datetime(
    2025,
    1,
    1,
    tzinfo=timezone.utc,
)

def run_market_evidence_cli(
    *,
    completed_through: date,
    output_format: str = "text",
) -> str:
    credentials = (
        load_alpaca_credentials_from_environment()
    )

    vix_csv_text = (
        fetch_official_vix_history()
    )

    stock_client = StockHistoricalDataClient(
        credentials.api_key,
        credentials.secret_key,
    )

    demo_arguments = {
        "stock_client": stock_client,
        "vix_csv_text": vix_csv_text,
        "completed_through": completed_through,
        "start": DEFAULT_HISTORY_START,
    }

    if output_format == "text":
        return run_market_evidence_demo(
            **demo_arguments
        )

    if output_format == "html":
        return run_visual_market_evidence_demo(
            **demo_arguments
        )

    raise ValueError(
        "unsupported_demo_format"
    )


def _completed_date(
    value: str,
) -> date:
    try:
        return date.fromisoformat(
            value
        )
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "completed-through must use YYYY-MM-DD"
        ) from error


def _print_fail_closed(
    reason: str,
) -> None:
    print(
        "LOCKEAN DEMO FAILED CLOSED"
    )
    print(
        f"REASON: {reason}"
    )
    print(
        "BROKER ORDER SUBMITTED: NO"
    )


def main(
    argv=None,
) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Render a read-only Lockean "
            "market-evidence decision report."
        ),
    )

    parser.add_argument(
        "--completed-through",
        required=True,
        type=_completed_date,
        help="Completed market session, YYYY-MM-DD",
    )

    parser.add_argument(
        "--format",
        dest="output_format",
        choices=(
            "text",
            "html",
        ),
        default="text",
        help="Report format.",
    )

    parser.add_argument(
        "--output",
        help=(
            "Optional file path for rendered output."
        ),
    )

    args = parser.parse_args(
        argv
    )

    try:
        output = run_market_evidence_cli(
            completed_through=(
                args.completed_through
            ),
            output_format=(
                args.output_format
            ),
        )
    except ValueError as error:
        _print_fail_closed(
            str(error)
        )
        return 1

    if args.output:
        output_path = Path(
            args.output
        )

        try:
            output_path.write_text(
                output,
                encoding="utf-8",
            )
        except OSError:
            _print_fail_closed(
                "demo_output_write_failed"
            )
            return 1

        print(
            "LOCKEAN DEMO OUTPUT WRITTEN"
        )
        print(
            f"FORMAT: {args.output_format.upper()}"
        )
        print(
            f"PATH: {output_path}"
        )

        return 0

    print(
        output
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )