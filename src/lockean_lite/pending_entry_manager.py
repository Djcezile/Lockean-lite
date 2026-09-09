from dataclasses import dataclass
from datetime import datetime, timezone

from lockean_lite.paper_portfolio_snapshot import (
    PaperPortfolioSnapshot,
)


@dataclass(frozen=True)
class PendingEntryMaintenanceResult:
    reason: str
    cancelled_order_ids: tuple[str, ...] = ()
    active_order_ids: tuple[str, ...] = ()


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def maintain_pending_entry_orders(
    *,
    trading_client,
    snapshot: PaperPortfolioSnapshot,
    timeout_seconds: int = 240,
    now_fn=None,
) -> PendingEntryMaintenanceResult:
    if timeout_seconds <= 0:
        raise ValueError(
            "entry_order_timeout_seconds_must_be_positive"
        )

    now = (
        now_fn()
        if now_fn is not None
        else datetime.now(timezone.utc)
    )

    cancelled_ids: list[str] = []
    active_ids: list[str] = []

    for order in getattr(
        snapshot,
        "pending_mleg_orders",
        (),
    ):
        if order.purpose != "entry":
            continue

        if order.submitted_at is None:
            # Without a broker timestamp there is no safe basis
            # for declaring the order stale. Keep reserving risk.
            if order.order_id:
                active_ids.append(order.order_id)
            continue

        age_seconds = (
            _normalize_datetime(now)
            - _normalize_datetime(order.submitted_at)
        ).total_seconds()

        if age_seconds < timeout_seconds:
            if order.order_id:
                active_ids.append(order.order_id)
            continue

        if not order.order_id:
            raise ValueError(
                "stale_entry_order_id_missing"
            )

        trading_client.cancel_order_by_id(
            order.order_id
        )
        cancelled_ids.append(order.order_id)

    if cancelled_ids:
        return PendingEntryMaintenanceResult(
            reason="stale_entry_order_cancelled",
            cancelled_order_ids=tuple(cancelled_ids),
            active_order_ids=tuple(active_ids),
        )

    if active_ids:
        return PendingEntryMaintenanceResult(
            reason="pending_entry_order_active",
            active_order_ids=tuple(active_ids),
        )

    return PendingEntryMaintenanceResult(
        reason="no_pending_entry_order"
    )
