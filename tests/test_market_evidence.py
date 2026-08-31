from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from lockean_lite.market_evidence import (
    MarketBar,
    MarketEvidence,
)


def test_market_evidence_preserves_immutable_raw_market_facts():
    bar = MarketBar(
        timestamp=datetime(
            2026,
            8,
            28,
            20,
            0,
            tzinfo=timezone.utc,
        ),
        open=Decimal("510.00"),
        high=Decimal("512.00"),
        low=Decimal("509.50"),
        close=Decimal("511.75"),
        volume=1000000,
    )

    evidence = MarketEvidence(
        evidence_id="evidence-001",
        symbol="SPY",
        as_of=datetime(
            2026,
            8,
            28,
            20,
            0,
            tzinfo=timezone.utc,
        ),
        source="alpaca",
        bars=(bar,),
    )

    assert evidence.symbol == "SPY"
    assert evidence.source == "alpaca"
    assert evidence.bars == (bar,)

    with pytest.raises(FrozenInstanceError):
        evidence.symbol = "QQQ"