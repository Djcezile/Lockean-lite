from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from lockean_lite.market_evidence_demo import (
    run_market_evidence_demo,
)


COMPLETED_THROUGH = date(
    2026,
    8,
    31,
)

START = datetime(
    2025,
    9,
    1,
    tzinfo=timezone.utc,
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


def test_real_market_demo_uses_existing_evidence_and_report_boundaries(
    monkeypatch,
):
    calls = []

    monkeypatch.setattr(
        "lockean_lite.market_evidence_demo.read_spy_daily_evidence",
        lambda **kwargs: (
            calls.append(
                (
                    "spy",
                    kwargs,
                )
            )
            or _spy_evidence()
        ),
    )

    monkeypatch.setattr(
        "lockean_lite.market_evidence_demo.read_cboe_vix_daily_evidence",
        lambda **kwargs: (
            calls.append(
                (
                    "vix",
                    kwargs,
                )
            )
            or _vix_evidence()
        ),
    )

    report = SimpleNamespace(
        status="REJECTED",
        reason="breakout_filter_failed",
    )

    monkeypatch.setattr(
        "lockean_lite.market_evidence_demo.build_market_decision_report",
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
        "lockean_lite.market_evidence_demo.render_market_decision_report",
        lambda value: (
            calls.append(
                (
                    "render",
                    value,
                )
            )
            or "LOCKEAN DECISION REPORT"
        ),
    )

    output = run_market_evidence_demo(
        stock_client="stock-client",
        vix_csv_text="csv-data",
        completed_through=COMPLETED_THROUGH,
        start=START,
    )

    assert output == (
        "LOCKEAN DECISION REPORT"
    )

    assert calls[0][0] == "spy"
    assert calls[1][0] == "vix"
    assert calls[2][0] == "report"
    assert calls[3][0] == "render"

    assert calls[0][1] == {
        "client": "stock-client",
        "completed_through": COMPLETED_THROUGH,
        "start": START,
    }

    assert calls[1][1] == {
        "csv_text": "csv-data",
        "completed_through": COMPLETED_THROUGH,
    }


def test_real_market_demo_passes_exact_ingested_evidence_into_report(
    monkeypatch,
):
    spy = _spy_evidence()
    vix = _vix_evidence()

    captured = {}

    monkeypatch.setattr(
        "lockean_lite.market_evidence_demo.read_spy_daily_evidence",
        lambda **kwargs: spy,
    )

    monkeypatch.setattr(
        "lockean_lite.market_evidence_demo.read_cboe_vix_daily_evidence",
        lambda **kwargs: vix,
    )

    monkeypatch.setattr(
        "lockean_lite.market_evidence_demo.build_market_decision_report",
        lambda **kwargs: (
            captured.update(
                kwargs
            )
            or SimpleNamespace()
        ),
    )

    monkeypatch.setattr(
        "lockean_lite.market_evidence_demo.render_market_decision_report",
        lambda report: "rendered",
    )

    run_market_evidence_demo(
        stock_client="stock-client",
        vix_csv_text="csv-data",
        completed_through=COMPLETED_THROUGH,
        start=START,
    )

    assert captured == {
        "spy_evidence": spy,
        "vix_evidence": vix,
    }


def test_real_market_demo_propagates_missing_evidence_failure(
    monkeypatch,
):
    monkeypatch.setattr(
        "lockean_lite.market_evidence_demo.read_spy_daily_evidence",
        lambda **kwargs: _spy_evidence(),
    )

    def missing_vix(**kwargs):
        raise ValueError(
            "vix_completed_session_missing"
        )

    monkeypatch.setattr(
        "lockean_lite.market_evidence_demo.read_cboe_vix_daily_evidence",
        missing_vix,
    )

    try:
        run_market_evidence_demo(
            stock_client="stock-client",
            vix_csv_text="csv-data",
            completed_through=COMPLETED_THROUGH,
            start=START,
        )
    except ValueError as error:
        assert str(error) == (
            "vix_completed_session_missing"
        )
    else:
        raise AssertionError(
            "missing VIX evidence must fail closed"
        )


def test_real_market_demo_has_no_execution_dependencies():
    import lockean_lite.market_evidence_demo as demo

    forbidden_names = (
        "LockeanAuthority",
        "PaperExecutionGateway",
        "StructuredAIRecommendationProvider",
        "execute_authorized_paper_order",
        "issue_authorization_receipt",
    )

    for name in forbidden_names:
        assert not hasattr(
            demo,
            name,
        )