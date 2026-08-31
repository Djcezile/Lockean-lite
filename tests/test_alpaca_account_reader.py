from lockean_lite.alpaca_account_reader import (
    read_paper_account_from_environment,
)


def test_paper_account_reader_performs_account_read_only(monkeypatch):
    calls = []

    class FakeTradingClient:
        def get_account(self):
            calls.append("get_account")
            return "paper-account"

    monkeypatch.setattr(
        "lockean_lite.alpaca_account_reader.create_paper_trading_client_from_environment",
        lambda: FakeTradingClient(),
    )

    account = read_paper_account_from_environment()

    assert account == "paper-account"
    assert calls == ["get_account"]