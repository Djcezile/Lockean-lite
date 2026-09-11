from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from alpaca.common.enums import Sort
from alpaca.data.enums import DataFeed
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame


NEW_YORK = ZoneInfo("America/New_York")
_PERCENT_QUANTUM = Decimal("0.001")


def _percent_change(current: Decimal, prior: Decimal) -> Decimal | None:
    if prior <= 0:
        return None

    return (
        ((current - prior) / prior) * Decimal("100")
    ).quantize(_PERCENT_QUANTUM)


def _format_percent(value: Decimal | None) -> str:
    return "NA" if value is None else str(value)


def _direction(value: Decimal | None) -> str:
    if value is None:
        return "NA"
    if value > 0:
        return "UP"
    if value < 0:
        return "DOWN"
    return "FLAT"


def read_spy_intraday_context(
    *,
    client,
    now: datetime | None = None,
    lookback_minutes: int = 90,
) -> dict[str, str]:
    if lookback_minutes < 30:
        raise ValueError("intraday_lookback_too_short")

    current_time = now or datetime.now(timezone.utc)

    if current_time.tzinfo is None:
        raise ValueError("intraday_now_must_be_timezone_aware")

    request = StockBarsRequest(
        symbol_or_symbols="SPY",
        timeframe=TimeFrame.Minute,
        start=(
            current_time
            - timedelta(minutes=lookback_minutes)
        ),
        end=current_time,
        sort=Sort.ASC,
        feed=DataFeed.IEX,
    )

    response = client.get_stock_bars(request)
    raw_bars = tuple(response.data.get("SPY", ()))
    current_session = current_time.astimezone(NEW_YORK).date()

    bars = tuple(
        bar
        for bar in raw_bars
        if (
            bar.timestamp.astimezone(NEW_YORK).date()
            == current_session
            and bar.timestamp <= current_time
        )
    )

    if not bars:
        raise ValueError("intraday_spy_bars_unavailable")

    closes = tuple(
        Decimal(str(bar.close))
        for bar in bars
    )

    latest_close = closes[-1]
    since_open = _percent_change(
        latest_close,
        closes[0],
    )

    def horizon(minutes: int) -> Decimal | None:
        if len(closes) <= minutes:
            return None
        return _percent_change(
            latest_close,
            closes[-1 - minutes],
        )

    return_5m = horizon(5)
    return_15m = horizon(15)
    return_30m = horizon(30)

    return {
        "intraday_status": (
            "AVAILABLE"
            if len(closes) >= 16
            else "WARMING_UP"
        ),
        "intraday_source": "alpaca_iex_minute",
        "intraday_as_of": bars[-1].timestamp.isoformat(),
        "intraday_bar_count": str(len(bars)),
        "intraday_spy_close": str(latest_close),
        "intraday_return_since_open_pct": _format_percent(
            since_open
        ),
        "intraday_return_5m_pct": _format_percent(
            return_5m
        ),
        "intraday_return_15m_pct": _format_percent(
            return_15m
        ),
        "intraday_return_30m_pct": _format_percent(
            return_30m
        ),
        "intraday_direction_5m": _direction(return_5m),
        "intraday_direction_15m": _direction(return_15m),
        "intraday_direction_30m": _direction(return_30m),
    }
