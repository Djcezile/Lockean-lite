import pytest

from lockean_lite.alpaca_credentials import (
    load_alpaca_credentials_from_environment,
)


def test_alpaca_credentials_fail_closed_when_secret_key_is_missing(monkeypatch):
    monkeypatch.setenv(
        "ALPACA_API_KEY",
        "demo-key",
    )
    monkeypatch.delenv(
        "ALPACA_SECRET_KEY",
        raising=False,
    )

    with pytest.raises(
        ValueError,
        match="missing_alpaca_credentials: ALPACA_SECRET_KEY",
    ):
        load_alpaca_credentials_from_environment()

def test_alpaca_credentials_load_exact_values_and_are_immutable(monkeypatch):
    monkeypatch.setenv(
        "ALPACA_API_KEY",
        "demo-key",
    )
    monkeypatch.setenv(
        "ALPACA_SECRET_KEY",
        "demo-secret",
    )

    credentials = load_alpaca_credentials_from_environment()

    assert credentials.api_key == "demo-key"
    assert credentials.secret_key == "demo-secret"

    with pytest.raises(AttributeError):
        credentials.api_key = "changed-key"

def test_alpaca_credentials_fail_closed_when_api_key_is_missing(monkeypatch):
    monkeypatch.delenv(
        "ALPACA_API_KEY",
        raising=False,
    )
    monkeypatch.setenv(
        "ALPACA_SECRET_KEY",
        "demo-secret",
    )

    with pytest.raises(
        ValueError,
        match="missing_alpaca_credentials: ALPACA_API_KEY",
    ):
        load_alpaca_credentials_from_environment()