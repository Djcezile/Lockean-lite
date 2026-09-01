from datetime import date, datetime, timezone
from types import SimpleNamespace

from lockean_lite.visual_market_evidence_demo import (
    run_visual_market_evidence_demo,
)


COMPLETED_THROUGH = date(
    2026,
    8,
    31,
)

START = datetime(
    2025,
    1,
    1,
    tzinfo=timezone.utc,
)


def test_visual_demo_uses_existing_market_evidence_report(
    monkeypatch,
):
    report = SimpleNamespace(
        status="REJECTED",
        reason="breakout_filter_failed",
    )

    calls = []

    monkeypatch.setattr(
        "lockean_lite.visual_market_evidence_demo.build_market_evidence_report",
        lambda **kwargs: (
            calls.append(
                (
                    "report",
                    kwargs,
                )
            )
            or report
        ),
    )

    monkeypatch.setattr(
        "lockean_lite.visual_market_evidence_demo.render_market_decision_html",
        lambda value: (
            calls.append(
                (
                    "html",
                    value,
                )
            )
            or "<html>LOCKEAN</html>"
        ),
    )

    output = run_visual_market_evidence_demo(
        stock_client="stock-client",
        vix_csv_text="vix-csv",
        completed_through=COMPLETED_THROUGH,
        start=START,
    )

    assert output == (
        "<html>LOCKEAN</html>"
    )

    assert calls == [
        (
            "report",
            {
                "stock_client": "stock-client",
                "vix_csv_text": "vix-csv",
                "completed_through": COMPLETED_THROUGH,
                "start": START,
            },
        ),
        (
            "html",
            report,
        ),
    ]


def test_visual_demo_passes_exact_report_to_html_renderer(
    monkeypatch,
):
    report = object()
    captured = {}

    monkeypatch.setattr(
        "lockean_lite.visual_market_evidence_demo.build_market_evidence_report",
        lambda **kwargs: report,
    )

    def renderer(value):
        captured["report"] = value
        return "<html></html>"

    monkeypatch.setattr(
        "lockean_lite.visual_market_evidence_demo.render_market_decision_html",
        renderer,
    )

    run_visual_market_evidence_demo(
        stock_client="stock-client",
        vix_csv_text="vix-csv",
        completed_through=COMPLETED_THROUGH,
        start=START,
    )

    assert captured["report"] is report


def test_visual_demo_propagates_report_failure(
    monkeypatch,
):
    def failed_report(**kwargs):
        raise ValueError(
            "vix_completed_session_missing"
        )

    monkeypatch.setattr(
        "lockean_lite.visual_market_evidence_demo.build_market_evidence_report",
        failed_report,
    )

    try:
        run_visual_market_evidence_demo(
            stock_client="stock-client",
            vix_csv_text="vix-csv",
            completed_through=COMPLETED_THROUGH,
            start=START,
        )
    except ValueError as error:
        assert str(error) == (
            "vix_completed_session_missing"
        )
    else:
        raise AssertionError(
            "visual demo must fail closed"
        )


def test_visual_demo_has_no_decision_or_execution_authority():
    import lockean_lite.visual_market_evidence_demo as visual

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