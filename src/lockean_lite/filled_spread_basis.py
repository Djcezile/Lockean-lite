from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal

from alpaca.trading.enums import QueryOrderStatus
from alpaca.trading.requests import GetOrdersRequest


_HISTORY_LIMIT = 500


def _decimal(value) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _enum_text(value) -> str:
    if value is None:
        return ""
    enum_value = getattr(value, "value", None)
    if enum_value is not None:
        return str(enum_value)
    return str(value)


def _normalize_datetime(value) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    return datetime.min.replace(tzinfo=timezone.utc)


def _integral_filled_units(order) -> int:
    filled_qty = abs(_decimal(getattr(order, "filled_qty", 0)))
    if filled_qty <= 0:
        return 0
    if filled_qty != filled_qty.to_integral_value():
        return 0
    return int(filled_qty)


def _order_structure_and_purpose(order):
    order_class = _enum_text(
        getattr(order, "order_class", "")
    ).lower()
    if order_class != "mleg":
        return None

    legs = tuple(getattr(order, "legs", ()) or ())
    if len(legs) != 2:
        return None

    symbols = tuple(
        str(getattr(leg, "symbol", ""))
        for leg in legs
    )
    if any(not symbol for symbol in symbols):
        return None

    intents = tuple(
        _enum_text(
            getattr(leg, "position_intent", "")
        ).lower()
        for leg in legs
    )

    if intents and all("to_open" in intent for intent in intents):
        purpose = "entry"
    elif intents and all("to_close" in intent for intent in intents):
        purpose = "exit"
    else:
        return None

    return frozenset(symbols), purpose


def _entry_debit(order) -> Decimal:
    filled_price = _decimal(
        getattr(order, "filled_avg_price", None)
    )
    if filled_price > 0:
        return filled_price

    # A filled debit MLEG was authorized and submitted with a positive parent
    # limit debit.  If Alpaca omits the parent filled average, the positive
    # limit is a conservative basis: an actual debit fill cannot be worse
    # than its buy-limit ceiling.
    limit_price = _decimal(
        getattr(order, "limit_price", None)
    )
    if limit_price > 0:
        return limit_price

    return Decimal("0")


def read_open_spread_entry_basis(*, trading_client):
    """Recover remaining open debit lots from broker closed MLEG history.

    Alpaca can report per-leg option cost bases that do not preserve the
    original net debit of a filled multi-leg order across sessions.  This
    function rebuilds the remaining opening lots from authoritative filled
    MLEG parent orders.  Filled closing orders consume opening lots FIFO.

    Structures whose history is incomplete are omitted so callers can fail
    closed rather than invent an entry basis.
    """

    orders = trading_client.get_orders(
        filter=GetOrdersRequest(
            status=QueryOrderStatus.CLOSED,
            limit=_HISTORY_LIMIT,
            nested=True,
        )
    )

    ordered = sorted(
        orders,
        key=lambda order: _normalize_datetime(
            getattr(order, "submitted_at", None)
        ),
    )

    lots = defaultdict(list)
    complete = defaultdict(lambda: True)

    for order in ordered:
        parsed = _order_structure_and_purpose(order)
        if parsed is None:
            continue

        structure, purpose = parsed
        units = _integral_filled_units(order)
        if units <= 0:
            continue

        if purpose == "entry":
            price = _entry_debit(order)
            if price <= 0:
                complete[structure] = False
                lots[structure].clear()
                continue

            for _ in range(units):
                lots[structure].append(price)
            continue

        # Alpaca positions are netted. Treat filled closing MLEGs as FIFO
        # consumption of the opening lots for the exact same structure.
        for _ in range(units):
            if not lots[structure]:
                complete[structure] = False
                break
            lots[structure].pop(0)

    recovered = {}
    for structure, remaining_lots in lots.items():
        if not complete[structure] or not remaining_lots:
            continue
        recovered[structure] = (
            sum(remaining_lots, start=Decimal("0"))
            / Decimal(len(remaining_lots))
        )

    return recovered
