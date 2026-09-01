from datetime import date, datetime

from lockean_lite.market_evidence_demo import (
    build_market_evidence_report,
)
from lockean_lite.visual_decision_report import (
    render_market_decision_html,
)


def run_visual_market_evidence_demo(
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

    return render_market_decision_html(
        report
    )