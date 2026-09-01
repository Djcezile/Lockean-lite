import argparse
from datetime import date, datetime, timezone
from urllib.error import URLError
from urllib.request import Request, urlopen

from alpaca.data.historical import (
    StockHistoricalDataClient,
)

from lockean_lite.alpaca_credentials import (
    load_alpaca_credentials_from_environment,
)
from lockean_lite.market_evidence_demo import (
    run_market_evidence_demo,
)


VIX_HISTORY_URL = (
    "https://cdn.cboe.com/api/global/us_indices/"
    "daily_prices/VIX_History.csv"
)

DEFAULT_HISTORY_START = datetime(
    2025,
    1,
    1,
    tzinfo=timezone.utc,
)


def fetch_official_vix_history() -> str:
    request = Request(
        VIX_HISTORY_URL,
        headers={
            "User-Agent": "Lockean-Lite/1.0",
        },
    )

    try:
        with urlopen(
            request,
            timeout=15,
        ) as response:
            return response.read().decode(
                "utf-8-sig"
            )
    except (
        URLError,
        OSError,
        UnicodeDecodeError,
    ) as error:
        raise ValueError(
            "vix_evidence_unavailable"
        ) from error


def run_market_evidence_cli(
    *,
    completed_through: date,
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

    return run_market_evidence_demo(
        stock_client=stock_client,
        vix_csv_text=vix_csv_text,
        completed_through=completed_through,
        start=DEFAULT_HISTORY_START,
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

    args = parser.parse_args(
        argv
    )

    try:
        output = run_market_evidence_cli(
            completed_through=(
                args.completed_through
            ),
        )
    except ValueError as error:
        print(
            "LOCKEAN DEMO FAILED CLOSED"
        )
        print(
            f"REASON: {error}"
        )
        print(
            "BROKER ORDER SUBMITTED: NO"
        )
        return 1

    print(
        output
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )