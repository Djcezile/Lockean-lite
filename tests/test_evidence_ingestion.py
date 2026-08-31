from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

from lockean_lite.evidence_ingestion import (
    canonical_session_close,
    read_cboe_vix_daily_evidence,
    read_spy_daily_evidence,
)


COMPLETED_THROUGH = date(
    2026,
    8,
    28,
)


from datetime import timedelta


class FakeStockDataClient:
    def get_stock_bars(self, request):
        start_date = date(
            2026,
            2,
            10,
        )

        bars = []

        for index in range(200):
            session_date = (
                start_date
                + timedelta(days=index)
            )

            if index == 199:
                session_date = COMPLETED_THROUGH

            timestamp = datetime(
                session_date.year,
                session_date.month,
                session_date.day,
                4,
                0,
                tzinfo=timezone.utc,
            )

            bars.append(
                SimpleNamespace(
                    timestamp=timestamp,
                    open=500,
                    high=505,
                    low=495,
                    close=502,
                    volume=1_000_000,
                )
            )

        return SimpleNamespace(
            data={
                "SPY": bars,
            }
        )


def test_session_close_is_normalized_to_new_york_close():
    result = canonical_session_close(
        COMPLETED_THROUGH
    )

    assert result == datetime(
        2026,
        8,
        28,
        20,
        0,
        tzinfo=timezone.utc,
    )


def test_spy_evidence_is_normalized_into_lockean_market_evidence():
    evidence = read_spy_daily_evidence(
        client=FakeStockDataClient(),
        completed_through=COMPLETED_THROUGH,
        start=datetime(
            2025,
            10,
            1,
            tzinfo=timezone.utc,
        ),
    )

    assert evidence.symbol == "SPY"
    assert evidence.source == "alpaca"
    assert len(evidence.bars) == 200
    assert (
        evidence.as_of
        == canonical_session_close(
            COMPLETED_THROUGH
        )
    )


def test_vix_evidence_is_normalized_from_cboe_history():
    csv_text = (
        "DATE,OPEN,HIGH,LOW,CLOSE\n"
        + "\n".join(
            (
                f"08/{day:02d}/2026,"
                "15.00,16.00,14.00,15.50"
            )
            for day in range(1, 29)
        )
    )

    evidence = read_cboe_vix_daily_evidence(
        csv_text=csv_text,
        completed_through=COMPLETED_THROUGH,
    )

    assert evidence.symbol == "VIX"
    assert evidence.source == "cboe"
    assert (
        evidence.as_of
        == canonical_session_close(
            COMPLETED_THROUGH
        )
    )


def test_vix_evidence_fails_when_completed_session_is_missing():
    csv_text = (
        "DATE,OPEN,HIGH,LOW,CLOSE\n"
        + "\n".join(
            (
                f"08/{day:02d}/2026,"
                "15.00,16.00,14.00,15.50"
            )
            for day in range(1, 28)
        )
    )

    with pytest.raises(
        ValueError,
        match="vix_completed_session_missing",
    ):
        read_cboe_vix_daily_evidence(
            csv_text=csv_text,
            completed_through=COMPLETED_THROUGH,
        )