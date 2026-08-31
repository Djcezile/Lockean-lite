from decimal import Decimal
from dataclasses import dataclass

from lockean_lite.market_evidence import MarketEvidence

@dataclass(frozen=True)
class MarketEntryEvaluation:
    passed: bool
    reason: str

def evaluate_market_entry_policy(
    spy_evidence: MarketEvidence,
    vix_evidence: MarketEvidence,
) -> MarketEntryEvaluation:
    if not bullish_trend_filter_passes(spy_evidence):
        return MarketEntryEvaluation(
            passed=False,
            reason="trend_filter_failed",
        )

    if not momentum_filter_passes(spy_evidence):
        return MarketEntryEvaluation(
            passed=False,
            reason="momentum_filter_failed",
        )

    if not breakout_filter_passes(spy_evidence):
        return MarketEntryEvaluation(
            passed=False,
            reason="breakout_filter_failed",
        )

    if not volatility_filter_passes(vix_evidence):
        return MarketEntryEvaluation(
            passed=False,
            reason="volatility_filter_failed",
        )

    return MarketEntryEvaluation(
        passed=True,
        reason="entry_conditions_satisfied",
    )


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


def _calculate_rsi_14(
    evidence: MarketEvidence,
) -> Decimal | None:
    closes = tuple(
        bar.close
        for bar in evidence.bars
    )

    if len(closes) < 15:
        return None

    changes = tuple(
        closes[index] - closes[index - 1]
        for index in range(1, len(closes))
    )

    gains = tuple(
        change if change > 0 else Decimal("0")
        for change in changes
    )

    losses = tuple(
        -change if change < 0 else Decimal("0")
        for change in changes
    )

    average_gain = (
        sum(gains[:14], start=Decimal("0"))
        / Decimal("14")
    )

    average_loss = (
        sum(losses[:14], start=Decimal("0"))
        / Decimal("14")
    )

    for index in range(14, len(changes)):
        average_gain = (
            (average_gain * Decimal("13"))
            + gains[index]
        ) / Decimal("14")

        average_loss = (
            (average_loss * Decimal("13"))
            + losses[index]
        ) / Decimal("14")

    if average_gain == 0 and average_loss == 0:
        return Decimal("50")

    if average_loss == 0:
        return Decimal("100")

    relative_strength = average_gain / average_loss

    return Decimal("100") - (
        Decimal("100")
        / (Decimal("1") + relative_strength)
    )


def momentum_filter_passes(
    evidence: MarketEvidence,
) -> bool:
    rsi_14 = _calculate_rsi_14(evidence)

    if rsi_14 is None:
        return False

    return (
        Decimal("50") < rsi_14
        and rsi_14 < Decimal("70")
    )


def breakout_filter_passes(
    evidence: MarketEvidence,
) -> bool:
    bars = evidence.bars

    if len(bars) < 21:
        return False

    latest_close = bars[-1].close

    previous_20_session_high = max(
        bar.high
        for bar in bars[-21:-1]
    )

    return latest_close > previous_20_session_high


def volatility_filter_passes(
    evidence: MarketEvidence,
) -> bool:
    closes = tuple(
        bar.close
        for bar in evidence.bars
    )

    if len(closes) < 20:
        return False

    vix_sma_20 = sum(
        closes[-20:],
        start=Decimal("0"),
    ) / Decimal("20")

    return closes[-1] < vix_sma_20