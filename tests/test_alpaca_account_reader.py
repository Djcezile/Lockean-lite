from lockean_lite.alpaca_account_reader import (
    read_paper_account_from_environment,
    read_paper_account_snapshot_from_environment,
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

def test_paper_account_snapshot_reader_translates_authenticated_account(monkeypatch):
    raw_account = object()
    expected_snapshot = object()
    captured = {}

    monkeypatch.setattr(
        "lockean_lite.alpaca_account_reader.read_paper_account_from_environment",
        lambda: raw_account,
    )

    def fake_create_paper_account_snapshot(account):
        captured["account"] = account
        return expected_snapshot

    monkeypatch.setattr(
        "lockean_lite.alpaca_account_reader.create_paper_account_snapshot",
        fake_create_paper_account_snapshot,
    )

    snapshot = read_paper_account_snapshot_from_environment()

    assert captured["account"] is raw_account
    assert snapshot is expected_snapshot