from decimal import Decimal

from lockean_lite.market_evidence import MarketEvidence


def bullish_trend_filter_passes(
    evidence: MarketEvidence,
) -> bool:
    closes = tuple(
        bar.close
        for bar in evidence.bars
    )

    if len(closes) < 200:
        return False

    latest_close = closes[-1]

    sma_50 = sum(
        closes[-50:],
        start=Decimal("0"),
    ) / Decimal("50")

    sma_200 = sum(
        closes[-200:],
        start=Decimal("0"),
    ) / Decimal("200")

    return (
        latest_close > sma_50
        and sma_50 > sma_200
    )