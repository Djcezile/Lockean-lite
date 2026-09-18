from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from alpaca.trading.enums import QueryOrderStatus
from alpaca.trading.requests import GetOrdersRequest


_HISTORY_LIMIT = 500


@dataclass(frozen=True)
class SpreadBasisRecoveryDiagnostics:
    closed_orders_returned: int
    parsed_mleg_orders: int
    entry_orders_recognized: int
    exit_orders_recognized: int
    missing_position_intent_orders: int
    missing_filled_price_entries: int
    missing_filled_avg_price_entries: int
    limit_price_fallback_entries: int
    fifo_underflow_structures: int
    recovered_structures: int


@dataclass(frozen=True)
class SpreadBasisRecoveryResult:
    basis_by_structure: dict[frozenset[str], Decimal]
    diagnostics: SpreadBasisRecoveryDiagnostics


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


def _classify_mleg_order(order):
    order_class = _enum_text(
        getattr(order, "order_class", "")
    ).lower()
    if order_class != "mleg":
        return None, None, "not_mleg"

    legs = tuple(getattr(order, "legs", ()) or ())
    if len(legs) != 2:
        return None, None, "leg_count_invalid"

    symbols = tuple(
        str(getattr(leg, "symbol", ""))
        for leg in legs
    )
    if any(not symbol for symbol in symbols):
        return None, None, "leg_symbol_missing"

    intents = tuple(
        _enum_text(
            getattr(leg, "position_intent", "")
        ).lower()
        for leg in legs
    )

    if not intents or any(not intent for intent in intents):
        return frozenset(symbols), None, "position_intent_missing"

    if all("to_open" in intent for intent in intents):
        purpose = "entry"
    elif all("to_close" in intent for intent in intents):
        purpose = "exit"
    else:
        return frozenset(symbols), None, "position_intent_mixed"

    return frozenset(symbols), purpose, None


def _entry_debit(order) -> tuple[Decimal, bool, bool]:
    raw_filled_price = getattr(order, "filled_avg_price", None)
    filled_price = _decimal(raw_filled_price)
    filled_avg_missing = raw_filled_price is None or filled_price <= 0

    if filled_price > 0:
        return filled_price, False, False

    # A filled debit MLEG was authorized and submitted with a positive parent
    # limit debit. If Alpaca omits the parent filled average, the positive
    # limit is a conservative basis: an actual debit fill cannot be worse
    # than its buy-limit ceiling.
    limit_price = _decimal(
        getattr(order, "limit_price", None)
    )
    if limit_price > 0:
        return limit_price, True, True

    return Decimal("0"), filled_avg_missing, False


def recover_open_spread_entry_basis(
    *,
    trading_client,
) -> SpreadBasisRecoveryResult:
    """Recover remaining open debit lots and explain the recovery path.

    This function is read-only. It queries closed Alpaca orders with nested
    legs, reconstructs exact two-leg MLEG structures, and consumes filled
    closing lots FIFO. Any structure with incomplete history is omitted so
    callers can fail closed rather than invent an entry basis.
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

    parsed_mleg_orders = 0
    entry_orders_recognized = 0
    exit_orders_recognized = 0
    missing_position_intent_orders = 0
    missing_filled_price_entries = 0
    missing_filled_avg_price_entries = 0
    limit_price_fallback_entries = 0
    fifo_underflow_structures: set[frozenset[str]] = set()

    for order in ordered:
        structure, purpose, reason = _classify_mleg_order(order)

        if reason == "position_intent_missing":
            missing_position_intent_orders += 1
            if structure is not None:
                complete[structure] = False
                lots[structure].clear()
            continue

        if reason is not None:
            continue

        parsed_mleg_orders += 1
        units = _integral_filled_units(order)
        if units <= 0:
            continue

        if purpose == "entry":
            entry_orders_recognized += 1
            price, filled_avg_missing, used_limit_fallback = (
                _entry_debit(order)
            )

            if filled_avg_missing:
                missing_filled_avg_price_entries += 1

            if used_limit_fallback:
                limit_price_fallback_entries += 1

            if price <= 0:
                missing_filled_price_entries += 1
                complete[structure] = False
                lots[structure].clear()
                continue

            if not complete[structure]:
                # Historical ambiguity for this exact structure must remain
                # fail-closed even when a later entry looks valid.
                continue

            for _ in range(units):
                lots[structure].append(price)
            continue

        exit_orders_recognized += 1

        for _ in range(units):
            if not lots[structure]:
                complete[structure] = False
                fifo_underflow_structures.add(structure)
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

    diagnostics = SpreadBasisRecoveryDiagnostics(
        closed_orders_returned=len(orders),
        parsed_mleg_orders=parsed_mleg_orders,
        entry_orders_recognized=entry_orders_recognized,
        exit_orders_recognized=exit_orders_recognized,
        missing_position_intent_orders=(
            missing_position_intent_orders
        ),
        missing_filled_price_entries=(
            missing_filled_price_entries
        ),
        missing_filled_avg_price_entries=(
            missing_filled_avg_price_entries
        ),
        limit_price_fallback_entries=(
            limit_price_fallback_entries
        ),
        fifo_underflow_structures=len(
            fifo_underflow_structures
        ),
        recovered_structures=len(recovered),
    )

    return SpreadBasisRecoveryResult(
        basis_by_structure=recovered,
        diagnostics=diagnostics,
    )


def read_open_spread_entry_basis(*, trading_client):
    """Compatibility wrapper returning only recovered entry basis."""

    return recover_open_spread_entry_basis(
        trading_client=trading_client
    ).basis_by_structure


def _structure_text(structure: frozenset[str]) -> str:
    return "/".join(sorted(structure))


def render_spread_basis_recovery_report(
    result: SpreadBasisRecoveryResult,
) -> str:
    """Render non-sensitive diagnostics for the read-only broker probe."""

    diagnostic = result.diagnostics

    lines = [
        "LOCKEAN SPREAD BASIS RECOVERY PROBE",
        "===================================",
        "MODE: READ ONLY",
        (
            "closed_orders_returned="
            f"{diagnostic.closed_orders_returned}"
        ),
        (
            "parsed_mleg_orders="
            f"{diagnostic.parsed_mleg_orders}"
        ),
        (
            "entry_orders_recognized="
            f"{diagnostic.entry_orders_recognized}"
        ),
        (
            "exit_orders_recognized="
            f"{diagnostic.exit_orders_recognized}"
        ),
        (
            "missing_position_intent_orders="
            f"{diagnostic.missing_position_intent_orders}"
        ),
        (
            "missing_filled_avg_price_entries="
            f"{diagnostic.missing_filled_avg_price_entries}"
        ),
        (
            "missing_usable_price_entries="
            f"{diagnostic.missing_filled_price_entries}"
        ),
        (
            "limit_price_fallback_entries="
            f"{diagnostic.limit_price_fallback_entries}"
        ),
        (
            "fifo_underflow_structures="
            f"{diagnostic.fifo_underflow_structures}"
        ),
        (
            "recovered_structures="
            f"{diagnostic.recovered_structures}"
        ),
    ]

    for structure, basis in sorted(
        result.basis_by_structure.items(),
        key=lambda item: sorted(item[0]),
    ):
        lines.append(
            "RECOVERED STRUCTURE: "
            f"{_structure_text(structure)} | "
            f"entry_debit={basis}"
        )

    return "\n".join(lines)
