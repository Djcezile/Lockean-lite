from decimal import Decimal

from lockean_lite.profitability_scorecard import (
    build_profitability_scorecard,
    render_profitability_scorecard,
)


def test_scorecard_uses_broker_money_results_as_the_outcome():
    scorecard = build_profitability_scorecard(
        opening_equity=Decimal("99400.07"),
        closing_equity=Decimal("99425.37"),
        broker_day_pl=Decimal("25.30"),
        entry_evaluations=8,
    )

    assert scorecard.equity_change == Decimal("25.30")
    assert scorecard.broker_day_pl == Decimal("25.30")
    assert scorecard.outcome == "POSITIVE"
    assert scorecard.profitable is True

    rendered = render_profitability_scorecard(scorecard)
    assert "PROFITABILITY SCORECARD" in rendered
    assert "NET EQUITY CHANGE: $25.30" in rendered
    assert "BROKER DAY P&L: $25.30" in rendered
    assert "OUTCOME: POSITIVE" in rendered


def test_scorecard_does_not_call_a_negative_day_success():
    scorecard = build_profitability_scorecard(
        opening_equity=Decimal("99423.37"),
        closing_equity=Decimal("99400.07"),
        broker_day_pl=Decimal("-23.30"),
        entry_evaluations=15,
    )

    assert scorecard.outcome == "NEGATIVE"
    assert scorecard.profitable is False


def test_scorecard_labels_unchanged_capital_flat():
    scorecard = build_profitability_scorecard(
        opening_equity=Decimal("99400.07"),
        closing_equity=Decimal("99400.07"),
        broker_day_pl=Decimal("0.00"),
        entry_evaluations=0,
    )

    assert scorecard.outcome == "FLAT"
    assert scorecard.profitable is False

