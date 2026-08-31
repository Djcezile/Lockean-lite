from dataclasses import FrozenInstanceError
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from lockean_lite.option_quote_snapshot import (
    OptionQuoteSnapshot,
)


def test_option_quote_snapshot_is_immutable_market_fact():
    quote = OptionQuoteSnapshot(
        contract_symbol="SPY260918C00782000",
        underlying_symbol="SPY",
        option_type="call",
        strike=Decimal("782"),
        expiration=date(2026, 9, 18),
        bid_price=Decimal("2.96"),
        ask_price=Decimal("3.03"),
        quote_timestamp=datetime(
            2026,
            8,
            28,
            19,
            59,
            59,
            tzinfo=timezone.utc,
        ),
        source="alpaca",
    )

    assert quote.strike == Decimal("782")
    assert quote.ask_price == Decimal("3.03")
    assert quote.source == "alpaca"

    with pytest.raises(FrozenInstanceError):
        quote.ask_price = Decimal("1.00")