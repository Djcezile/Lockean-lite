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