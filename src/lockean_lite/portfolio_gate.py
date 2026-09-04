from dataclasses import dataclass
from decimal import Decimal

from lockean_lite.paper_portfolio_snapshot import (
    PaperPortfolioSnapshot,
)


@dataclass(frozen=True)
class PortfolioEntryDecision:
    allowed: bool
    reason: str


def evaluate_portfolio_entry(
    *,
    snapshot: PaperPortfolioSnapshot,
    maximum_open_spreads: int = 5,
    maximum_daily_loss: Decimal = Decimal("750.00"),
) -> PortfolioEntryDecision:
    if maximum_open_spreads <= 0:
        raise ValueError(
            "maximum_open_spreads_must_be_positive"
        )

    if maximum_daily_loss <= 0:
        raise ValueError(
            "maximum_daily_loss_must_be_positive"
        )

    if snapshot.status != "ACTIVE":
        return PortfolioEntryDecision(
            allowed=False,
            reason="account_not_active",
        )

    if snapshot.trading_blocked:
        return PortfolioEntryDecision(
            allowed=False,
            reason="account_trading_blocked",
        )

    if snapshot.options_buying_power <= 0:
        return PortfolioEntryDecision(
            allowed=False,
            reason="options_buying_power_exhausted",
        )

    if snapshot.day_pl <= -maximum_daily_loss:
        return PortfolioEntryDecision(
            allowed=False,
            reason="daily_loss_limit_reached",
        )

    pending_spread_units = int(
        getattr(
            snapshot,
            "pending_spread_units",
            0,
        )
    )

    committed_spreads = (
        snapshot.managed_spreads
        + pending_spread_units
    )

    if committed_spreads >= maximum_open_spreads:
        return PortfolioEntryDecision(
            allowed=False,
            reason="portfolio_spread_limit_reached",
        )

    return PortfolioEntryDecision(
        allowed=True,
        reason="portfolio_entry_allowed",
    )
