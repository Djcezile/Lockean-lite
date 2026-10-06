from decimal import Decimal

from lockean_lite.market_entry_policy import (
    breakout_filter_passes,
    bullish_trend_filter_passes,
    calculate_rsi_14,
    momentum_filter_passes,
    previous_session_high,
    simple_moving_average,
    volatility_filter_passes,
)


_SESSION_PERCENT_QUANTUM = Decimal("0.001")
_SIGNAL_METRIC_QUANTUM = Decimal("0.001")


def _format_signal_metric(value: Decimal | None) -> str:
    if value is None:
        return "NA"
    return format(value.quantize(_SIGNAL_METRIC_QUANTUM), "f")


def _completed_session_text(evidence) -> str:
    as_of = getattr(evidence, "as_of", None)
    if as_of is None or not hasattr(as_of, "date"):
        return "UNKNOWN"
    return as_of.date().isoformat()


def _distance_percent(
    *,
    value: Decimal,
    reference: Decimal | None,
) -> Decimal | None:
    if reference is None or reference <= 0:
        return None
    return (
        ((value - reference) / reference) * Decimal("100")
    ).quantize(_SIGNAL_METRIC_QUANTUM)


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
    spy_sma_50 = simple_moving_average(spy_evidence, 50)
    spy_sma_200 = simple_moving_average(spy_evidence, 200)
    spy_rsi_14 = calculate_rsi_14(spy_evidence)
    spy_previous_20_session_high = previous_session_high(
        spy_evidence,
        20,
    )
    vix_close = Decimal(str(vix_evidence.bars[-1].close))
    vix_sma_20 = simple_moving_average(vix_evidence, 20)

    context = {
        "spy_completed_through": _completed_session_text(spy_evidence),
        "spy_close": str(prior_close),
        "spy_sma_50": _format_signal_metric(spy_sma_50),
        "spy_sma_200": _format_signal_metric(spy_sma_200),
        "spy_rsi_14": _format_signal_metric(spy_rsi_14),
        "spy_previous_20_session_high": _format_signal_metric(
            spy_previous_20_session_high
        ),
        "spy_breakout_distance_pct": _format_signal_metric(
            _distance_percent(
                value=prior_close,
                reference=spy_previous_20_session_high,
            )
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
        "vix_completed_through": _completed_session_text(vix_evidence),
        "vix_close": str(vix_close),
        "vix_sma_20": _format_signal_metric(vix_sma_20),
        "vix_distance_from_sma_20_pct": _format_signal_metric(
            _distance_percent(
                value=vix_close,
                reference=vix_sma_20,
            )
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
