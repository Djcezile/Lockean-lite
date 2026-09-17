from decimal import Decimal

from lockean_lite.market_entry_policy import (
    breakout_filter_passes,
    bullish_trend_filter_passes,
    momentum_filter_passes,
    volatility_filter_passes,
)


_SESSION_PERCENT_QUANTUM = Decimal("0.001")


def _session_return_percent(
    *,
    current: Decimal,
    prior_close: Decimal,
) -> Decimal | None:
    if prior_close <= 0 or current <= 0:
        return None

    return (
        ((current - prior_close) / prior_close)
        * Decimal("100")
    ).quantize(_SESSION_PERCENT_QUANTUM)


def _direction(value: Decimal) -> str:
    if value > 0:
        return "UP"
    if value < 0:
        return "DOWN"
    return "FLAT"


def build_agent_market_context(
    *,
    spy_evidence,
    vix_evidence,
    intraday_context: dict[str, str] | None = None,
) -> dict[str, str]:
    prior_close = Decimal(str(spy_evidence.bars[-1].close))

    context = {
        "spy_close": str(prior_close),
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
        # Preserve the original spy_close key for backward compatibility,
        # while naming its temporal meaning explicitly for the agent.
        context["spy_prior_close"] = str(prior_close)
        context.update(intraday_context)

        current_text = intraday_context.get(
            "intraday_spy_close"
        )
        if current_text is not None:
            try:
                current = Decimal(str(current_text))
            except (ValueError, TypeError, ArithmeticError):
                current = Decimal("0")

            session_return = _session_return_percent(
                current=current,
                prior_close=prior_close,
            )
            if session_return is not None:
                context["spy_session_return_pct"] = str(
                    session_return
                )
                context["spy_session_direction"] = _direction(
                    session_return
                )

    return context
