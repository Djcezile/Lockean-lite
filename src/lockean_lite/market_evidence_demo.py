from datetime import date, datetime

from lockean_lite.decision_report import (
    MarketDecisionReport,
    build_market_decision_report,
    render_market_decision_report,
)
from lockean_lite.evidence_ingestion import (
    read_cboe_vix_daily_evidence,
    read_spy_daily_evidence,
)


def build_market_evidence_report(
    *,
    stock_client,
    vix_csv_text: str,
    completed_through: date,
    start: datetime,
) -> MarketDecisionReport:
    spy_evidence = read_spy_daily_evidence(
        client=stock_client,
        completed_through=completed_through,
        start=start,
    )

    vix_evidence = read_cboe_vix_daily_evidence(
        csv_text=vix_csv_text,
        completed_through=completed_through,
    )

    return build_market_decision_report(
        spy_evidence=spy_evidence,
        vix_evidence=vix_evidence,
    )


def run_market_evidence_demo(
    *,
    stock_client,
    vix_csv_text: str,
    completed_through: date,
    start: datetime,
) -> str:
    report = build_market_evidence_report(
        stock_client=stock_client,
        vix_csv_text=vix_csv_text,
        completed_through=completed_through,
        start=start,
    )

    return render_market_decision_report(
        report
    )