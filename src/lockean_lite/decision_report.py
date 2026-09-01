from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from lockean_lite.market_entry_policy import (
    bullish_trend_filter_passes,
    momentum_filter_passes,
    breakout_filter_passes,
    volatility_filter_passes,
    evaluate_market_entry_policy,
)


@dataclass(frozen=True)
class MarketDecisionReport:
    as_of: datetime

    spy_source: str
    vix_source: str

    spy_close: Decimal
    vix_close: Decimal

    trend_passed: bool
    momentum_passed: bool
    breakout_passed: bool
    volatility_passed: bool

    status: str
    reason: str

    ai_recommendation_reached: bool
    authority_reached: bool
    receipt_issued: bool
    broker_order_submitted: bool


def build_market_decision_report(
    *,
    spy_evidence,
    vix_evidence,
) -> MarketDecisionReport:
    if (
        spy_evidence.as_of
        != vix_evidence.as_of
    ):
        raise ValueError(
            "report_evidence_as_of_mismatch"
        )

    trend_passed = (
        bullish_trend_filter_passes(
            spy_evidence
        )
    )

    momentum_passed = (
        momentum_filter_passes(
            spy_evidence
        )
    )

    breakout_passed = (
        breakout_filter_passes(
            spy_evidence
        )
    )

    volatility_passed = (
        volatility_filter_passes(
            vix_evidence
        )
    )

    evaluation = (
        evaluate_market_entry_policy(
            spy_evidence=spy_evidence,
            vix_evidence=vix_evidence,
        )
    )

    status = (
        "ELIGIBLE_FOR_NEXT_STAGE"
        if evaluation.passed
        else "REJECTED"
    )

    return MarketDecisionReport(
        as_of=spy_evidence.as_of,

        spy_source=spy_evidence.source,
        vix_source=vix_evidence.source,

        spy_close=(
            spy_evidence.bars[-1].close
        ),
        vix_close=(
            vix_evidence.bars[-1].close
        ),

        trend_passed=trend_passed,
        momentum_passed=momentum_passed,
        breakout_passed=breakout_passed,
        volatility_passed=volatility_passed,

        status=status,
        reason=evaluation.reason,

        ai_recommendation_reached=False,
        authority_reached=False,
        receipt_issued=False,
        broker_order_submitted=False,
    )


def _pass_fail(
    value: bool,
) -> str:
    return (
        "PASS"
        if value
        else "FAIL"
    )


def render_market_decision_report(
    report: MarketDecisionReport,
) -> str:
    return "\n".join(
        (
            "========================================",
            "LOCKEAN DECISION REPORT",
            "========================================",
            f"As of: {report.as_of.isoformat()}",
            "",
            "VERIFIABLE MARKET EVIDENCE",
            (
                f"SPY / Alpaca: "
                f"{report.spy_close}"
            ),
            (
                f"VIX / Cboe: "
                f"{report.vix_close}"
            ),
            "",
            "DETERMINISTIC ENTRY CONDITIONS",
            (
                "Trend: "
                f"{_pass_fail(report.trend_passed)}"
            ),
            (
                "Momentum: "
                f"{_pass_fail(report.momentum_passed)}"
            ),
            (
                "Breakout: "
                f"{_pass_fail(report.breakout_passed)}"
            ),
            (
                "Volatility: "
                f"{_pass_fail(report.volatility_passed)}"
            ),
            "",
            f"DECISION: {report.status}",
            f"REASON: {report.reason}",
            "",
            "DOWNSTREAM AUTHORITY",
            (
                "AI RECOMMENDATION REACHED: "
                f"{'YES' if report.ai_recommendation_reached else 'NO'}"
            ),
            (
                "AUTHORITY REACHED: "
                f"{'YES' if report.authority_reached else 'NO'}"
            ),
            (
                "AUTHORIZATION RECEIPT ISSUED: "
                f"{'YES' if report.receipt_issued else 'NO'}"
            ),
            (
                "BROKER ORDER SUBMITTED: "
                f"{'YES' if report.broker_order_submitted else 'NO'}"
            ),
            "========================================",
        )
    )