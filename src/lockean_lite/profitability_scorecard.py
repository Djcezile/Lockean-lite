from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ProfitabilityScorecard:
    opening_equity: Decimal
    closing_equity: Decimal
    equity_change: Decimal
    broker_day_pl: Decimal
    entry_evaluations: int
    outcome: str
    broker_profitable: bool
    all_in_net_pl: Decimal | None
    all_in_profitable: bool | None


def build_profitability_scorecard(
    *,
    opening_equity: Decimal,
    closing_equity: Decimal,
    broker_day_pl: Decimal,
    entry_evaluations: int,
) -> ProfitabilityScorecard:
    if opening_equity <= 0 or closing_equity < 0:
        raise ValueError("profitability_equity_invalid")
    if entry_evaluations < 0:
        raise ValueError(
            "profitability_entry_evaluations_must_be_non_negative"
        )

    equity_change = closing_equity - opening_equity

    if broker_day_pl > 0:
        outcome = "POSITIVE"
    elif broker_day_pl < 0:
        outcome = "NEGATIVE"
    else:
        outcome = "FLAT"

    return ProfitabilityScorecard(
        opening_equity=opening_equity,
        closing_equity=closing_equity,
        equity_change=equity_change,
        broker_day_pl=broker_day_pl,
        entry_evaluations=entry_evaluations,
        outcome=outcome,
        broker_profitable=broker_day_pl > 0,
        all_in_net_pl=None,
        all_in_profitable=None,
    )


def _money(value: Decimal) -> str:
    return f"${value:.2f}"


def render_profitability_scorecard(
    scorecard: ProfitabilityScorecard,
) -> str:
    return "\n".join(
        (
            "PROFITABILITY SCORECARD",
            "=======================",
            "SCOPE: BROKER ACCOUNT ONLY",
            f"OPENING EQUITY: {_money(scorecard.opening_equity)}",
            f"CLOSING EQUITY: {_money(scorecard.closing_equity)}",
            f"NET EQUITY CHANGE: {_money(scorecard.equity_change)}",
            f"BROKER DAY P&L: {_money(scorecard.broker_day_pl)}",
            f"ENTRY EVALUATIONS: {scorecard.entry_evaluations}",
            f"BROKER OUTCOME: {scorecard.outcome}",
            "OPERATING COSTS: NOT TRACKED",
            "ALL-IN NET P&L: UNKNOWN",
        )
    )
