from dataclasses import dataclass
from decimal import Decimal

from lockean_lite.paper_portfolio_snapshot import (
    PaperPortfolioSnapshot,
)


@dataclass(frozen=True)
class PortfolioEntryDecision:
    allowed: bool
    reason: str


def _committed_spread_units(snapshot: PaperPortfolioSnapshot) -> int:
    pending_orders = getattr(
        snapshot,
        "pending_mleg_orders",
        (),
    )

    if pending_orders:
        pending_entry_units = int(
            getattr(
                snapshot,
                "pending_entry_spread_units",
                0,
            )
        )
        pending_unknown_units = int(
            getattr(
                snapshot,
                "pending_unknown_spread_units",
                0,
            )
        )
        pending_risk_units = (
            pending_entry_units
            + pending_unknown_units
        )
    else:
        # Backward-compatible conservative behavior for
        # snapshots created before order-purpose tracking.
        pending_risk_units = int(
            getattr(
                snapshot,
                "pending_spread_units",
                0,
            )
        )

    return snapshot.managed_spreads + pending_risk_units


def evaluate_session_stop_loss_capacity(
    *,
    snapshot: PaperPortfolioSnapshot,
    remaining_capacity: int,
) -> PortfolioEntryDecision:
    if remaining_capacity < 0:
        raise ValueError(
            "remaining_session_stop_loss_capacity_must_be_non_negative"
        )

    if _committed_spread_units(snapshot) >= remaining_capacity:
        return PortfolioEntryDecision(
            allowed=False,
            reason="session_stop_loss_capacity_reached",
        )

    return PortfolioEntryDecision(
        allowed=True,
        reason="session_stop_loss_capacity_available",
    )


def evaluate_portfolio_entry(
    *,
    snapshot: PaperPortfolioSnapshot,
    maximum_open_spreads: int = 5,
    maximum_daily_loss: Decimal = Decimal("750.00"),
    remaining_session_stop_loss_capacity: int | None = None,
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

    committed_spreads = _committed_spread_units(snapshot)

    if remaining_session_stop_loss_capacity is not None:
        capacity_decision = evaluate_session_stop_loss_capacity(
            snapshot=snapshot,
            remaining_capacity=remaining_session_stop_loss_capacity,
        )
        if not capacity_decision.allowed:
            return capacity_decision

    if committed_spreads >= maximum_open_spreads:
        return PortfolioEntryDecision(
            allowed=False,
            reason="portfolio_spread_limit_reached",
        )

    return PortfolioEntryDecision(
        allowed=True,
        reason="portfolio_entry_allowed",
    )
