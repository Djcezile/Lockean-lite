import json
import os
import subprocess

from decimal import (
    Decimal,
    InvalidOperation,
)

from lockean_lite.paper_account_snapshot import (
    PaperAccountSnapshot,
)

CLI_TIMEOUT_SECONDS = 10

REQUIRED_ACCOUNT_FIELDS = (
    "status",
    "currency",
    "trading_blocked",
    "options_buying_power",
    "options_approved_level",
    "options_trading_level",
)


def read_paper_account_snapshot_from_cli(
    *,
    runner=subprocess.run,
) -> PaperAccountSnapshot:
    live_trade_value = os.getenv(
        "ALPACA_LIVE_TRADE"
    )

    if (
        live_trade_value is not None
        and live_trade_value.strip().lower()
        not in (
            "",
            "false",
            "0",
        )
    ):
        raise ValueError(
            "alpaca_cli_live_trading_forbidden"
        )

    try:
        completed = runner(
            [
                "alpaca",
                "api",
                "GET",
                "/v2/account",
                "--quiet",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=CLI_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as error:
        raise ValueError(
            "alpaca_cli_unavailable"
        ) from error
    except subprocess.TimeoutExpired as error:
        raise ValueError(
            "alpaca_cli_timeout"
        ) from error

    if completed.returncode != 0:
        raise ValueError(
            "alpaca_cli_account_read_failed"
        )

    try:
        data = json.loads(
            completed.stdout
        )
    except json.JSONDecodeError as error:
        raise ValueError(
            "alpaca_cli_account_response_invalid"
        ) from error

    if not isinstance(data, dict):
        raise ValueError(
            "alpaca_cli_account_response_invalid"
        )

    if any(
        field not in data
        for field in REQUIRED_ACCOUNT_FIELDS
    ):
        raise ValueError(
            "alpaca_cli_account_response_invalid"
        )

    if (
        not isinstance(data["status"], str)
        or not isinstance(data["currency"], str)
        or not isinstance(
            data["trading_blocked"],
            bool,
        )
        or not isinstance(
            data["options_buying_power"],
            str,
        )
        or not isinstance(
            data["options_approved_level"],
            int,
        )
        or isinstance(
            data["options_approved_level"],
            bool,
        )
        or not isinstance(
            data["options_trading_level"],
            int,
        )
        or isinstance(
            data["options_trading_level"],
            bool,
        )
    ):
        raise ValueError(
            "alpaca_cli_account_response_invalid"
        )

    try:
        options_buying_power = Decimal(
            data["options_buying_power"]
        )
    except InvalidOperation as error:
        raise ValueError(
            "alpaca_cli_account_response_invalid"
        ) from error

    return PaperAccountSnapshot(
        status=data["status"],
        currency=data["currency"],
        trading_blocked=(
            data["trading_blocked"]
        ),
        options_buying_power=(
            options_buying_power
        ),
        options_approved_level=(
            data["options_approved_level"]
        ),
        options_trading_level=(
            data["options_trading_level"]
        ),
    )