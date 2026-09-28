from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

from alpaca.trading.enums import QueryOrderStatus
from alpaca.trading.requests import GetOrdersRequest


_NEW_YORK = ZoneInfo("America/New_York")
_STOP_LOSS_PREFIX = "lockean-sl-"
_STOP_LOSS_CALL_PREFIX = "lockean-sl-call-"
_STOP_LOSS_PUT_PREFIX = "lockean-sl-put-"
_TAKE_PROFIT_CALL_PREFIX = "lockean-tp-call-"
_TAKE_PROFIT_PUT_PREFIX = "lockean-tp-put-"


@dataclass(frozen=True)
class SessionLossLoopState:
    confirmed_stop_loss_fills: int
    blocked_direction: str | None
    cooldown_until: datetime | None
    halt_all_entries: bool
    reason: str


@dataclass(frozen=True)
class SessionLossLoopProposalDecision:
    allowed: bool
    reason: str


def build_managed_exit_client_order_id(
    *,
    reason: str,
    option_type: str,
) -> str:
    prefixes = {
        ("stop_loss_exit_submitted", "call"): _STOP_LOSS_CALL_PREFIX,
        ("stop_loss_exit_submitted", "put"): _STOP_LOSS_PUT_PREFIX,
        ("take_profit_exit_submitted", "call"): _TAKE_PROFIT_CALL_PREFIX,
        ("take_profit_exit_submitted", "put"): _TAKE_PROFIT_PUT_PREFIX,
    }
    prefix = prefixes.get((reason, option_type))
    if prefix is None:
        raise ValueError("managed_exit_client_order_tag_invalid")

    client_order_id = f"{prefix}{uuid4().hex}"
    if len(client_order_id) > 48:
        raise ValueError("managed_exit_client_order_tag_too_long")
    return client_order_id


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _session_bounds(now: datetime) -> tuple[datetime, datetime]:
    local_now = _normalize_datetime(now).astimezone(_NEW_YORK)
    local_start = datetime.combine(
        local_now.date(),
        datetime.min.time(),
        tzinfo=_NEW_YORK,
    )
    return (
        local_start.astimezone(timezone.utc),
        (local_start + timedelta(days=1)).astimezone(timezone.utc),
    )


def _tagged_stop_direction(client_order_id: str) -> str | None:
    if client_order_id.startswith(_STOP_LOSS_CALL_PREFIX):
        return "bullish"
    if client_order_id.startswith(_STOP_LOSS_PUT_PREFIX):
        return "bearish"
    if client_order_id.startswith(_STOP_LOSS_PREFIX):
        raise ValueError("stop_loss_order_direction_tag_invalid")
    return None


def read_session_loss_loop_state(
    *,
    trading_client,
    now: datetime,
    direction_cooldown_seconds: int = 3600,
    maximum_stop_loss_fills: int = 2,
) -> SessionLossLoopState:
    if direction_cooldown_seconds < 0:
        raise ValueError(
            "direction_cooldown_seconds_must_be_non_negative"
        )
    if maximum_stop_loss_fills <= 0:
        raise ValueError("maximum_stop_loss_fills_must_be_positive")

    normalized_now = _normalize_datetime(now)
    session_start, session_end = _session_bounds(normalized_now)
    orders = trading_client.get_orders(
        filter=GetOrdersRequest(
            status=QueryOrderStatus.CLOSED,
            after=session_start,
            until=normalized_now,
            limit=500,
            nested=True,
        )
    )

    fills: list[tuple[datetime, str, int]] = []
    seen_order_ids: set[str] = set()

    for order in orders:
        client_order_id = str(
            getattr(order, "client_order_id", "") or ""
        )
        direction = _tagged_stop_direction(client_order_id)
        if direction is None:
            continue

        filled_quantity = Decimal(
            str(getattr(order, "filled_qty", 0) or 0)
        )
        if filled_quantity <= 0:
            continue
        if filled_quantity != filled_quantity.to_integral_value():
            raise ValueError("stop_loss_filled_quantity_invalid")

        order_id = str(getattr(order, "id", "") or "")
        if not order_id:
            raise ValueError("stop_loss_filled_order_id_missing")
        if order_id in seen_order_ids:
            continue
        seen_order_ids.add(order_id)

        filled_at = getattr(order, "filled_at", None)
        if not isinstance(filled_at, datetime):
            raise ValueError("stop_loss_fill_time_missing")
        normalized_fill_time = _normalize_datetime(filled_at)
        if not session_start <= normalized_fill_time < session_end:
            continue

        fills.append(
            (
                normalized_fill_time,
                direction,
                int(filled_quantity),
            )
        )

    fills.sort(key=lambda item: item[0])
    confirmed_fills = sum(item[2] for item in fills)

    if confirmed_fills >= maximum_stop_loss_fills:
        return SessionLossLoopState(
            confirmed_stop_loss_fills=confirmed_fills,
            blocked_direction=None,
            cooldown_until=None,
            halt_all_entries=True,
            reason="session_stop_loss_limit_reached",
        )

    if fills:
        last_fill_time, last_direction, _ = fills[-1]
        cooldown_until = last_fill_time + timedelta(
            seconds=direction_cooldown_seconds
        )
        if normalized_now < cooldown_until:
            return SessionLossLoopState(
                confirmed_stop_loss_fills=confirmed_fills,
                blocked_direction=last_direction,
                cooldown_until=cooldown_until,
                halt_all_entries=False,
                reason="same_direction_stop_loss_cooldown",
            )

    return SessionLossLoopState(
        confirmed_stop_loss_fills=confirmed_fills,
        blocked_direction=None,
        cooldown_until=None,
        halt_all_entries=False,
        reason="loss_loop_entry_allowed",
    )


def _proposal_direction(proposal) -> str | None:
    option_types = {
        getattr(leg, "option_type", None)
        for leg in getattr(proposal, "legs", ())
    }
    if option_types == {"call"}:
        return "bullish"
    if option_types == {"put"}:
        return "bearish"
    return None


def evaluate_session_loss_loop_proposal(
    *,
    proposal,
    state: SessionLossLoopState,
) -> SessionLossLoopProposalDecision:
    if state.halt_all_entries:
        return SessionLossLoopProposalDecision(
            allowed=False,
            reason="session_stop_loss_limit_reached",
        )

    if state.blocked_direction is None:
        return SessionLossLoopProposalDecision(
            allowed=True,
            reason="loss_loop_proposal_allowed",
        )

    direction = _proposal_direction(proposal)
    if direction is None:
        return SessionLossLoopProposalDecision(
            allowed=False,
            reason="loss_loop_proposal_direction_ambiguous",
        )

    if direction == state.blocked_direction:
        return SessionLossLoopProposalDecision(
            allowed=False,
            reason="same_direction_stop_loss_cooldown_active",
        )

    return SessionLossLoopProposalDecision(
        allowed=True,
        reason="loss_loop_proposal_allowed",
    )
