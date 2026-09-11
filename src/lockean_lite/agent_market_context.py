from lockean_lite.market_entry_policy import (
    breakout_filter_passes,
    bullish_trend_filter_passes,
    momentum_filter_passes,
    volatility_filter_passes,
)


def build_agent_market_context(
    *,
    spy_evidence,
    vix_evidence,
    intraday_context: dict[str, str] | None = None,
) -> dict[str, str]:
    context = {
        "spy_close": str(
            spy_evidence.bars[-1].close
        ),
        "trend": (
            "PASS"
            if bullish_trend_filter_passes(
                spy_evidence
            )
            else "FAIL"
        ),
        "momentum": (
            "PASS"
            if momentum_filter_passes(
                spy_evidence
            )
            else "FAIL"
        ),
        "breakout": (
            "PASS"
            if breakout_filter_passes(
                spy_evidence
            )
            else "FAIL"
        ),
        "vix_close": str(
            vix_evidence.bars[-1].close
        ),
        "volatility": (
            "PASS"
            if volatility_filter_passes(
                vix_evidence
            )
            else "FAIL"
        ),
    }

    if intraday_context is not None:
        context.update(intraday_context)

    return context
