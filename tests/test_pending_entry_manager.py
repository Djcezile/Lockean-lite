from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from lockean_lite.paper_portfolio_snapshot import (
    PendingMlegOrderSnapshot,
)
from lockean_lite.pending_entry_manager import (
    maintain_pending_entry_orders,
)


class FakeTradingClient:
    def __init__(self):
        self.cancelled = []

    def cancel_order_by_id(self, order_id):
        self.cancelled.append(order_id)


def _snapshot(*orders):
    return SimpleNamespace(
        pending_mleg_orders=orders,
    )


def _order(
    *,
    order_id,
    purpose="entry",
    submitted_at,
):
    return PendingMlegOrderSnapshot(
        order_id=order_id,
        remaining_units=1,
        purpose=purpose,
        submitted_at=submitted_at,
        symbols=("SPY-A", "SPY-B"),
    )


def test_stale_entry_order_is_cancelled_and_requires_reconciliation():
    now = datetime(2026, 9, 9, 15, 0, tzinfo=timezone.utc)
    trading_client = FakeTradingClient()

    result = maintain_pending_entry_orders(
        trading_client=trading_client,
        snapshot=_snapshot(
            _order(
                order_id="entry-stale",
                submitted_at=now - timedelta(minutes=5),
            )
        ),
        timeout_seconds=240,
        now_fn=lambda: now,
    )

    assert result.reason == "stale_entry_order_cancelled"
    assert result.cancelled_order_ids == ("entry-stale",)
    assert result.active_order_ids == ()
    assert trading_client.cancelled == ["entry-stale"]


def test_fresh_entry_order_remains_active_and_keeps_reserved_capacity():
    now = datetime(2026, 9, 9, 15, 0, tzinfo=timezone.utc)
    trading_client = FakeTradingClient()

    result = maintain_pending_entry_orders(
        trading_client=trading_client,
        snapshot=_snapshot(
            _order(
                order_id="entry-live",
                submitted_at=now - timedelta(minutes=1),
            )
        ),
        timeout_seconds=240,
        now_fn=lambda: now,
    )

    assert result.reason == "pending_entry_order_active"
    assert result.cancelled_order_ids == ()
    assert result.active_order_ids == ("entry-live",)
    assert trading_client.cancelled == []


def test_exit_orders_are_not_touched_by_entry_order_maintenance():
    now = datetime(2026, 9, 9, 15, 0, tzinfo=timezone.utc)
    trading_client = FakeTradingClient()

    result = maintain_pending_entry_orders(
        trading_client=trading_client,
        snapshot=_snapshot(
            _order(
                order_id="exit-stale",
                purpose="exit",
                submitted_at=now - timedelta(minutes=10),
            )
        ),
        timeout_seconds=240,
        now_fn=lambda: now,
    )

    assert result.reason == "no_pending_entry_order"
    assert trading_client.cancelled == []


def test_entry_without_broker_timestamp_is_kept_conservatively_active():
    trading_client = FakeTradingClient()

    result = maintain_pending_entry_orders(
        trading_client=trading_client,
        snapshot=_snapshot(
            _order(
                order_id="entry-no-time",
                submitted_at=None,
            )
        ),
        timeout_seconds=240,
    )

    assert result.reason == "pending_entry_order_active"
    assert result.active_order_ids == ("entry-no-time",)
    assert trading_client.cancelled == []
