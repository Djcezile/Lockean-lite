import json
import os
import pytest
from decimal import Decimal
from subprocess import (
    CompletedProcess,
    TimeoutExpired,
)

from lockean_lite.alpaca_cli_account_reader import (
    read_paper_account_snapshot_from_cli,
)


def test_reads_valid_paper_account_snapshot_from_alpaca_cli():
    cli_account = {
        "status": "ACTIVE",
        "currency": "USD",
        "trading_blocked": False,
        "options_buying_power": "25000",
        "options_approved_level": 3,
        "options_trading_level": 3,
    }

    def fake_runner(*args, **kwargs):
        return CompletedProcess(
            args=args[0],
            returncode=0,
            stdout=json.dumps(cli_account),
            stderr="",
        )

    result = read_paper_account_snapshot_from_cli(
        runner=fake_runner,
    )

    assert result.status == "ACTIVE"
    assert result.currency == "USD"
    assert result.trading_blocked is False
    assert result.options_buying_power == Decimal("25000")
    assert result.options_approved_level == 3
    assert result.options_trading_level == 3

def test_fails_closed_when_alpaca_cli_returns_nonzero_exit_code():
    cli_account = {
        "status": "ACTIVE",
        "currency": "USD",
        "trading_blocked": False,
        "options_buying_power": "25000",
        "options_approved_level": 3,
        "options_trading_level": 3,
    }

    def fake_runner(*args, **kwargs):
        return CompletedProcess(
            args=args[0],
            returncode=2,
            stdout=json.dumps(cli_account),
            stderr='{"error":"authentication failed"}',
        )

    with pytest.raises(
        ValueError,
        match="alpaca_cli_account_read_failed",
    ):
        read_paper_account_snapshot_from_cli(
            runner=fake_runner,
        )

def test_fails_closed_when_alpaca_cli_returns_malformed_json():
    def fake_runner(*args, **kwargs):
        return CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="{not-valid-json",
            stderr="",
        )

    with pytest.raises(
        ValueError,
        match="alpaca_cli_account_response_invalid",
    ):
        read_paper_account_snapshot_from_cli(
            runner=fake_runner,
        )

def test_fails_closed_when_alpaca_cli_response_is_missing_required_field():
    cli_account = {
        "status": "ACTIVE",
        "currency": "USD",
        "trading_blocked": False,
        "options_buying_power": "25000",
        "options_approved_level": 3,
        # options_trading_level intentionally missing
    }

    def fake_runner(*args, **kwargs):
        return CompletedProcess(
            args=args[0],
            returncode=0,
            stdout=json.dumps(cli_account),
            stderr="",
        )

    with pytest.raises(
        ValueError,
        match="alpaca_cli_account_response_invalid",
    ):
        read_paper_account_snapshot_from_cli(
            runner=fake_runner,
        )


def test_fails_closed_when_alpaca_cli_response_has_invalid_field_types():
    cli_account = {
        "status": "ACTIVE",
        "currency": "USD",
        "trading_blocked": "false",
        "options_buying_power": "25000",
        "options_approved_level": 3,
        "options_trading_level": 3,
    }

    def fake_runner(*args, **kwargs):
        return CompletedProcess(
            args=args[0],
            returncode=0,
            stdout=json.dumps(cli_account),
            stderr="",
        )

    with pytest.raises(
        ValueError,
        match="alpaca_cli_account_response_invalid",
    ):
        read_paper_account_snapshot_from_cli(
            runner=fake_runner,
        )


def test_fails_closed_when_alpaca_cli_is_unavailable():
    def fake_runner(*args, **kwargs):
        raise FileNotFoundError(
            "alpaca executable not found"
        )

    with pytest.raises(
        ValueError,
        match="alpaca_cli_unavailable",
    ):
        read_paper_account_snapshot_from_cli(
            runner=fake_runner,
        )


def test_fails_closed_when_alpaca_cli_times_out():
    def fake_runner(*args, **kwargs):
        raise TimeoutExpired(
            cmd=args[0],
            timeout=10,
        )

    with pytest.raises(
        ValueError,
        match="alpaca_cli_timeout",
    ):
        read_paper_account_snapshot_from_cli(
            runner=fake_runner,
        )

def test_invokes_raw_alpaca_account_api_in_quiet_mode_with_timeout():
    cli_account = {
        "status": "ACTIVE",
        "currency": "USD",
        "trading_blocked": False,
        "options_buying_power": "25000",
        "options_approved_level": 3,
        "options_trading_level": 3,
    }

    captured = {}

    def fake_runner(*args, **kwargs):
        captured["args"] = args[0]
        captured["kwargs"] = kwargs

        return CompletedProcess(
            args=args[0],
            returncode=0,
            stdout=json.dumps(cli_account),
            stderr="",
        )

    read_paper_account_snapshot_from_cli(
        runner=fake_runner,
    )

    assert captured["args"] == [
        "alpaca",
        "api",
        "GET",
        "/v2/account",
        "--quiet",
    ]

    assert captured["kwargs"]["timeout"] == 10


def test_fails_closed_when_live_trading_is_enabled(monkeypatch):
    monkeypatch.setenv(
        "ALPACA_LIVE_TRADE",
        "true",
    )

    def fake_runner(*args, **kwargs):
        raise AssertionError(
            "CLI must not run in live mode"
        )

    with pytest.raises(
        ValueError,
        match="alpaca_cli_live_trading_forbidden",
    ):
        read_paper_account_snapshot_from_cli(
            runner=fake_runner,
        )


@pytest.mark.parametrize(
    "live_trade_value",
    [
        None,
        "",
        "false",
        "FALSE",
        "0",
    ],
)
def test_allows_non_live_trade_environment(
    monkeypatch,
    live_trade_value,
):
    cli_account = {
        "status": "ACTIVE",
        "currency": "USD",
        "trading_blocked": False,
        "options_buying_power": "25000",
        "options_approved_level": 3,
        "options_trading_level": 3,
    }

    if live_trade_value is None:
        monkeypatch.delenv(
            "ALPACA_LIVE_TRADE",
            raising=False,
        )
    else:
        monkeypatch.setenv(
            "ALPACA_LIVE_TRADE",
            live_trade_value,
        )

    def fake_runner(*args, **kwargs):
        return CompletedProcess(
            args=args[0],
            returncode=0,
            stdout=json.dumps(cli_account),
            stderr="",
        )

    result = read_paper_account_snapshot_from_cli(
        runner=fake_runner,
    )

    assert result.status == "ACTIVE"

def test_fails_closed_when_trading_blocked_field_is_missing():
    cli_account = {
        "status": "ACTIVE",
        "currency": "USD",
        # trading_blocked intentionally missing
        "options_buying_power": "25000",
        "options_approved_level": 3,
        "options_trading_level": 3,
    }

    def fake_runner(*args, **kwargs):
        return CompletedProcess(
            args=args[0],
            returncode=0,
            stdout=json.dumps(cli_account),
            stderr="",
        )

    with pytest.raises(
        ValueError,
        match="alpaca_cli_account_response_invalid",
    ):
        read_paper_account_snapshot_from_cli(
            runner=fake_runner,
        )