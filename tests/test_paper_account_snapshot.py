from decimal import Decimal
import pytest

from lockean_lite.paper_account_snapshot import (
    PaperAccountSnapshot,
    create_paper_account_snapshot,
)


def test_alpaca_account_is_translated_into_lockean_owned_snapshot():
    class FakeAccountStatus:
        value = "ACTIVE"

    class FakeAlpacaAccount:
        status = FakeAccountStatus()
        currency = "USD"
        trading_blocked = False
        options_buying_power = "2500.50"
        options_approved_level = 3
        options_trading_level = 3

    snapshot = create_paper_account_snapshot(
        FakeAlpacaAccount()
    )

    assert snapshot == PaperAccountSnapshot(
        status="ACTIVE",
        currency="USD",
        trading_blocked=False,
        options_buying_power=Decimal("2500.50"),
        options_approved_level=3,
        options_trading_level=3,
    )

def test_paper_account_snapshot_is_immutable():
    snapshot = PaperAccountSnapshot(
        status="ACTIVE",
        currency="USD",
        trading_blocked=False,
        options_buying_power=Decimal("2500.50"),
        options_approved_level=3,
        options_trading_level=3,
    )

    with pytest.raises(AttributeError):
        snapshot.options_trading_level = 4