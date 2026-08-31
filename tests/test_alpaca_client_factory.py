from lockean_lite.alpaca_client_factory import (
    create_paper_trading_client,
    create_paper_trading_client_from_environment,
)
from lockean_lite.alpaca_credentials import AlpacaCredentials


def test_alpaca_trading_client_is_always_created_in_paper_mode(monkeypatch):
    captured = {}

    class FakeTradingClient:
        def __init__(self, api_key, secret_key, paper):
            captured["api_key"] = api_key
            captured["secret_key"] = secret_key
            captured["paper"] = paper

    monkeypatch.setattr(
        "lockean_lite.alpaca_client_factory.TradingClient",
        FakeTradingClient,
    )

    client = create_paper_trading_client(
        api_key="demo-key",
        secret_key="demo-secret",
    )

    assert isinstance(client, FakeTradingClient)
    assert captured["api_key"] == "demo-key"
    assert captured["secret_key"] == "demo-secret"
    assert captured["paper"] is True

def test_paper_client_from_environment_uses_validated_credentials(monkeypatch):
    captured = {}

    credentials = AlpacaCredentials(
        api_key="demo-key",
        secret_key="demo-secret",
    )

    monkeypatch.setattr(
        "lockean_lite.alpaca_client_factory.load_alpaca_credentials_from_environment",
        lambda: credentials,
    )

    def fake_create_paper_trading_client(api_key, secret_key):
        captured["api_key"] = api_key
        captured["secret_key"] = secret_key
        return "paper-client"

    monkeypatch.setattr(
        "lockean_lite.alpaca_client_factory.create_paper_trading_client",
        fake_create_paper_trading_client,
    )

    client = create_paper_trading_client_from_environment()

    assert client == "paper-client"
    assert captured["api_key"] == "demo-key"
    assert captured["secret_key"] == "demo-secret"