from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from lockean_lite.intraday_market_context import (
    read_spy_intraday_context,
)


def _bar(timestamp, close):
    return SimpleNamespace(
        timestamp=timestamp,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1_000_000,
    )


class FakeStockClient:
    def __init__(self, bars):
        self.bars = bars
        self.request = None

    def get_stock_bars(self, request):
        self.request = request
        return SimpleNamespace(
            data={"SPY": self.bars},
        )


def test_intraday_context_exposes_live_multi_horizon_spy_returns():
    now = datetime(
        2026,
        9,
        11,
        15,
        0,
        tzinfo=timezone.utc,
    )

    start = now - timedelta(minutes=30)
    bars = tuple(
        _bar(
            start + timedelta(minutes=index),
            100 + index,
        )
        for index in range(31)
    )

    client = FakeStockClient(bars)

    result = read_spy_intraday_context(
        client=client,
        now=now,
    )

    assert result["intraday_status"] == "AVAILABLE"
    assert result["intraday_bar_count"] == "31"
    assert result["intraday_spy_close"] == "130"
    assert result["intraday_return_5m_pct"] == "4.000"
    assert result["intraday_return_15m_pct"] == "13.043"
    assert result["intraday_return_30m_pct"] == "30.000"
    assert result["intraday_direction_5m"] == "UP"
    assert result["intraday_direction_15m"] == "UP"
    assert result["intraday_direction_30m"] == "UP"
    assert result["intraday_return_since_open_pct"] == "30.000"
    assert client.request is not None


def test_intraday_context_reports_warming_up_without_inventing_missing_horizons():
    now = datetime(
        2026,
        9,
        11,
        13,
        32,
        tzinfo=timezone.utc,
    )

    bars = (
        _bar(now - timedelta(minutes=2), 100),
        _bar(now - timedelta(minutes=1), 101),
        _bar(now, 102),
    )

    result = read_spy_intraday_context(
        client=FakeStockClient(bars),
        now=now,
    )

    assert result["intraday_status"] == "WARMING_UP"
    assert result["intraday_return_5m_pct"] == "NA"
    assert result["intraday_return_15m_pct"] == "NA"
    assert result["intraday_return_30m_pct"] == "NA"
    assert result["intraday_direction_5m"] == "NA"
    assert result["intraday_return_since_open_pct"] == "2.000"
