import csv
from datetime import date, datetime, time
from decimal import Decimal
from io import StringIO
from zoneinfo import ZoneInfo

from alpaca.common.enums import Sort
from alpaca.data.enums import DataFeed
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from lockean_lite.market_evidence import (
    MarketBar,
    MarketEvidence,
)


NEW_YORK = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")


def canonical_session_close(
    session_date: date,
) -> datetime:
    local_close = datetime.combine(
        session_date,
        time(16, 0),
        tzinfo=NEW_YORK,
    )

    return local_close.astimezone(UTC)


def read_spy_daily_evidence(
    *,
    client,
    completed_through: date,
    start: datetime,
) -> MarketEvidence:
    request = StockBarsRequest(
        symbol_or_symbols="SPY",
        timeframe=TimeFrame.Day,
        start=start,
        end=canonical_session_close(
            completed_through
        ),
        sort=Sort.ASC,
        feed=DataFeed.IEX,
    )

    response = client.get_stock_bars(request)

    raw_bars = response.data["SPY"]

    completed = [
        bar
        for bar in raw_bars
        if bar.timestamp.astimezone(
            NEW_YORK
        ).date() <= completed_through
    ]

    if len(completed) < 200:
        raise ValueError(
            "insufficient_spy_history"
        )

    bars = tuple(
        MarketBar(
            timestamp=canonical_session_close(
                bar.timestamp.astimezone(
                    NEW_YORK
                ).date()
            ),
            open=Decimal(str(bar.open)),
            high=Decimal(str(bar.high)),
            low=Decimal(str(bar.low)),
            close=Decimal(str(bar.close)),
            volume=int(bar.volume),
        )
        for bar in completed
    )

    if (
        bars[-1].timestamp.date()
        != canonical_session_close(
            completed_through
        ).date()
    ):
        raise ValueError(
            "spy_completed_session_missing"
        )

    return MarketEvidence(
        evidence_id=(
            f"alpaca-spy-"
            f"{completed_through.isoformat()}"
        ),
        symbol="SPY",
        as_of=bars[-1].timestamp,
        source="alpaca",
        bars=bars,
    )


def read_cboe_vix_daily_evidence(
    *,
    csv_text: str,
    completed_through: date,
) -> MarketEvidence:
    reader = csv.DictReader(
        StringIO(csv_text)
    )

    rows = []

    for row in reader:
        session_date = datetime.strptime(
            row["DATE"],
            "%m/%d/%Y",
        ).date()

        if session_date > completed_through:
            continue

        rows.append(
            (
                session_date,
                Decimal(row["OPEN"]),
                Decimal(row["HIGH"]),
                Decimal(row["LOW"]),
                Decimal(row["CLOSE"]),
            )
        )

    rows.sort(
        key=lambda item: item[0]
    )

    if len(rows) < 20:
        raise ValueError(
            "insufficient_vix_history"
        )

    if rows[-1][0] != completed_through:
        raise ValueError(
            "vix_completed_session_missing"
        )

    bars = tuple(
        MarketBar(
            timestamp=canonical_session_close(
                session_date
            ),
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=0,
        )
        for (
            session_date,
            open_price,
            high_price,
            low_price,
            close_price,
        ) in rows
    )

    return MarketEvidence(
        evidence_id=(
            f"cboe-vix-"
            f"{completed_through.isoformat()}"
        ),
        symbol="VIX",
        as_of=bars[-1].timestamp,
        source="cboe",
        bars=bars,
    )