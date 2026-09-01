from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from lockean_lite.decision_report import (
    build_market_decision_report,
    render_market_decision_report,
)
from lockean_lite.market_entry_policy import (
    MarketEntryEvaluation,
)


AS_OF = datetime(
    2026,
    8,
    31,
    20,
    0,
    tzinfo=timezone.utc,
)


def _spy_evidence():
    return SimpleNamespace(
        source="alpaca",
        as_of=AS_OF,
        bars=(
            SimpleNamespace(
                close=Decimal("766.87"),
            ),
        ),
    )


def _vix_evidence():
    return SimpleNamespace(
        source="cboe",
        as_of=AS_OF,
        bars=(
            SimpleNamespace(
                close=Decimal("14.920000"),
            ),
        ),
    )


def _patch_real_aug31_result(
    monkeypatch,
):
    monkeypatch.setattr(
        "lockean_lite.decision_report.bullish_trend_filter_passes",
        lambda evidence: True,
    )

    monkeypatch.setattr(
        "lockean_lite.decision_report.momentum_filter_passes",
        lambda evidence: True,
    )

    monkeypatch.setattr(
        "lockean_lite.decision_report.breakout_filter_passes",
        lambda evidence: False,
    )

    monkeypatch.setattr(
        "lockean_lite.decision_report.volatility_filter_passes",
        lambda evidence: True,
    )

    monkeypatch.setattr(
        "lockean_lite.decision_report.evaluate_market_entry_policy",
        lambda **kwargs: MarketEntryEvaluation(
            passed=False,
            reason="breakout_filter_failed",
        ),
    )


def test_market_decision_report_preserves_real_evidence_and_exact_reason(
    monkeypatch,
):
    _patch_real_aug31_result(
        monkeypatch
    )

    report = build_market_decision_report(
        spy_evidence=_spy_evidence(),
        vix_evidence=_vix_evidence(),
    )

    assert report.as_of == AS_OF

    assert report.spy_source == "alpaca"
    assert report.vix_source == "cboe"

    assert report.spy_close == Decimal(
        "766.87"
    )

    assert report.vix_close == Decimal(
        "14.920000"
    )

    assert report.trend_passed is True
    assert report.momentum_passed is True
    assert report.breakout_passed is False
    assert report.volatility_passed is True

    assert report.status == "REJECTED"
    assert report.reason == (
        "breakout_filter_failed"
    )


def test_market_rejection_report_explicitly_shows_execution_was_not_reached(
    monkeypatch,
):
    _patch_real_aug31_result(
        monkeypatch
    )

    report = build_market_decision_report(
        spy_evidence=_spy_evidence(),
        vix_evidence=_vix_evidence(),
    )

    assert (
        report.ai_recommendation_reached
        is False
    )

    assert report.authority_reached is False
    assert report.receipt_issued is False
    assert report.broker_order_submitted is False


def test_market_decision_report_fails_closed_on_evidence_as_of_mismatch():
    mismatched_vix = SimpleNamespace(
        source="cboe",
        as_of=datetime(
            2026,
            8,
            28,
            20,
            0,
            tzinfo=timezone.utc,
        ),
        bars=(
            SimpleNamespace(
                close=Decimal("14.92"),
            ),
        ),
    )

    with pytest.raises(
        ValueError,
        match="report_evidence_as_of_mismatch",
    ):
        build_market_decision_report(
            spy_evidence=_spy_evidence(),
            vix_evidence=mismatched_vix,
        )


def test_market_decision_renderer_makes_lockean_reason_visible(
    monkeypatch,
):
    _patch_real_aug31_result(
        monkeypatch
    )

    report = build_market_decision_report(
        spy_evidence=_spy_evidence(),
        vix_evidence=_vix_evidence(),
    )

    rendered = render_market_decision_report(
        report
    )

    assert "LOCKEAN DECISION REPORT" in rendered
    assert "SPY / Alpaca" in rendered
    assert "VIX / Cboe" in rendered
    assert "Trend: PASS" in rendered
    assert "Momentum: PASS" in rendered
    assert "Breakout: FAIL" in rendered
    assert "Volatility: PASS" in rendered

    assert "DECISION: REJECTED" in rendered

    assert (
        "REASON: breakout_filter_failed"
        in rendered
    )

    assert (
        "BROKER ORDER SUBMITTED: NO"
        in rendered
    )