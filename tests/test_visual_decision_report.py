from datetime import datetime, timezone
from decimal import Decimal

from lockean_lite.decision_report import (
    MarketDecisionReport,
)
from lockean_lite.visual_decision_report import (
    render_market_decision_html,
)


AS_OF = datetime(
    2026,
    8,
    31,
    20,
    0,
    tzinfo=timezone.utc,
)


def _rejected_report():
    return MarketDecisionReport(
        as_of=AS_OF,
        spy_source="alpaca",
        vix_source="cboe",
        spy_close=Decimal("766.87"),
        vix_close=Decimal("14.920000"),
        trend_passed=True,
        momentum_passed=True,
        breakout_passed=False,
        volatility_passed=True,
        status="REJECTED",
        reason="breakout_filter_failed",
        ai_recommendation_reached=False,
        authority_reached=False,
        receipt_issued=False,
        broker_order_submitted=False,
    )


def test_visual_report_displays_exact_lockean_decision():
    html = render_market_decision_html(
        _rejected_report()
    )

    assert "LOCKEAN" in html
    assert "Independent AI Trade Authority" in html

    assert "766.87" in html
    assert "Alpaca" in html

    assert "14.920000" in html
    assert "Cboe" in html

    assert "REJECTED" in html
    assert "breakout_filter_failed" in html


def test_visual_report_displays_existing_condition_results_without_recalculation():
    html = render_market_decision_html(
        _rejected_report()
    )

    assert "Trend" in html
    assert "Momentum" in html
    assert "Breakout" in html
    assert "Volatility" in html

    assert html.count("PASS") == 3
    assert html.count("FAIL") == 1


def test_visual_report_exposes_downstream_components_that_were_not_reached():
    html = render_market_decision_html(
        _rejected_report()
    )

    assert "AI Recommendation" in html
    assert "NOT REACHED" in html

    assert "Authority" in html
    assert "Authorization Receipt" in html
    assert "NOT ISSUED" in html

    assert "Broker Order" in html
    assert "NO ORDER" in html


def test_visual_report_has_no_execution_authority_dependencies():
    import lockean_lite.visual_decision_report as visual

    forbidden_names = (
        "LockeanAuthority",
        "PaperExecutionGateway",
        "StructuredAIRecommendationProvider",
        "AuthorizationReceipt",
        "execute_authorized_paper_order",
        "issue_authorization_receipt",
        "evaluate_market_entry_policy",
        "bullish_trend_filter_passes",
        "momentum_filter_passes",
        "breakout_filter_passes",
        "volatility_filter_passes",
    )

    for name in forbidden_names:
        assert not hasattr(
            visual,
            name,
        )