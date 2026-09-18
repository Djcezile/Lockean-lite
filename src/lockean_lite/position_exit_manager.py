import re

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_DOWN

from alpaca.data.requests import (
    OptionLatestQuoteRequest,
)

from lockean_lite.alpaca_execution_adapter import (
    build_managed_spread_close_order,
)
from lockean_lite.paper_portfolio_snapshot import (
    PaperPortfolioSnapshot,
    PaperPositionSnapshot,
)


_OCC_OPTION_PATTERN = re.compile(
    r"^([A-Z]+)(\d{6})([CP])(\d{8})$"
)

# Preserve the original symbol parser constant for compatibility with any
# external diagnostics while the exit engine itself becomes directional.
_OCC_CALL_PATTERN = re.compile(
    r"^([A-Z]+)(\d{6})C(\d{8})$"
)


@dataclass(frozen=True)
class ManagedBullCallSpread:
    underlying: str
    expiration_code: str
    long_symbol: str
    short_symbol: str
    long_strike: Decimal
    short_strike: Decimal
    contracts: int
    entry_debit_per_contract: Decimal
    option_type: str = "call"


@dataclass(frozen=True)
class HistoryReconciledSpreadState:
    spreads: tuple[ManagedBullCallSpread, ...]
    unreconciled_option_symbols: tuple[str, ...]
    recovered_history_units: int
    reconciled_history_units: int


@dataclass(frozen=True)
class PaperSpreadExitResult:
    submitted: bool
    reason: str
    broker_order_id: str | None = None
    expected_return_percent: Decimal | None = None
    block_new_entries: bool = False
    cancelled_order_ids: tuple[str, ...] = ()
    observed_close_credit: Decimal | None = None
    submitted_limit_credit: Decimal | None = None
    submitted_limit_return_percent: Decimal | None = None
    entry_debit_per_contract: Decimal | None = None
    contracts: int | None = None
    long_symbol: str | None = None
    short_symbol: str | None = None
    diagnostics: tuple[str, ...] = ()


def _parse_option_contract(
    symbol: str,
) -> tuple[str, str, str, Decimal] | None:
    match = _OCC_OPTION_PATTERN.fullmatch(symbol)

    if match is None:
        return None

    underlying = match.group(1)
    expiration_code = match.group(2)
    option_type = (
        "call"
        if match.group(3) == "C"
        else "put"
    )
    strike = Decimal(match.group(4)) / Decimal("1000")

    return underlying, expiration_code, option_type, strike


def _parse_call_contract(
    symbol: str,
) -> tuple[str, str, Decimal] | None:
    parsed = _parse_option_contract(symbol)

    if parsed is None:
        return None

    underlying, expiration_code, option_type, strike = parsed

    if option_type != "call":
        return None

    return underlying, expiration_code, strike


def _integral_contract_quantity(
    position: PaperPositionSnapshot,
) -> int | None:
    quantity = abs(position.qty)

    if quantity <= 0:
        return None

    if quantity != quantity.to_integral_value():
        return None

    return int(quantity)


def _allocated_cost_basis(
    *,
    position: PaperPositionSnapshot,
    contracts: int,
) -> Decimal:
    total_contracts = _integral_contract_quantity(position)
    if total_contracts is None:
        raise ValueError("spread_position_quantity_invalid")

    return (
        abs(position.cost_basis)
        * Decimal(contracts)
        / Decimal(total_contracts)
    )


def _short_matches_long_vertical(
    *,
    option_type: str,
    long_strike: Decimal,
    short_strike: Decimal,
) -> bool:
    if option_type == "call":
        return short_strike > long_strike
    if option_type == "put":
        return short_strike < long_strike
    return False


def identify_managed_debit_spreads(
    snapshot: PaperPortfolioSnapshot,
    *,
    entry_basis_by_structure: dict[frozenset[str], Decimal] | None = None,
) -> tuple[ManagedBullCallSpread, ...]:
    long_positions: list[
        tuple[PaperPositionSnapshot, str, str, str, Decimal]
    ] = []
    short_positions: list[
        tuple[PaperPositionSnapshot, str, str, str, Decimal]
    ] = []

    for position in snapshot.positions:
        parsed = _parse_option_contract(position.symbol)

        if parsed is None:
            continue

        if _integral_contract_quantity(position) is None:
            continue

        underlying, expiration_code, option_type, strike = parsed
        item = (
            position,
            underlying,
            expiration_code,
            option_type,
            strike,
        )

        if position.qty > 0:
            long_positions.append(item)
        elif position.qty < 0:
            short_positions.append(item)

    long_positions.sort(
        key=lambda item: (item[1], item[2], item[3], item[4])
    )
    short_positions.sort(
        key=lambda item: (item[1], item[2], item[3], item[4])
    )

    # Alpaca aggregates identical option symbols. One long symbol can
    # therefore represent inventory belonging to several verticals.
    # Reconstruct by allocating integer inventory to the nearest valid
    # same-type short strike: higher for calls, lower for puts.
    short_remaining = [
        _integral_contract_quantity(item[0]) or 0
        for item in short_positions
    ]
    spreads: list[ManagedBullCallSpread] = []

    for (
        long_position,
        underlying,
        expiration_code,
        option_type,
        long_strike,
    ) in long_positions:
        long_remaining = (
            _integral_contract_quantity(long_position) or 0
        )

        while long_remaining > 0:
            matches = [
                index
                for index, item in enumerate(short_positions)
                if (
                    short_remaining[index] > 0
                    and item[1] == underlying
                    and item[2] == expiration_code
                    and item[3] == option_type
                    and _short_matches_long_vertical(
                        option_type=option_type,
                        long_strike=long_strike,
                        short_strike=item[4],
                    )
                )
            ]

            if not matches:
                break

            if option_type == "call":
                short_index = min(
                    matches,
                    key=lambda index: short_positions[index][4],
                )
            else:
                short_index = max(
                    matches,
                    key=lambda index: short_positions[index][4],
                )

            (
                short_position,
                _,
                _,
                _,
                short_strike,
            ) = short_positions[short_index]

            contracts = min(
                long_remaining,
                short_remaining[short_index],
            )

            long_cost = _allocated_cost_basis(
                position=long_position,
                contracts=contracts,
            )
            short_cost = _allocated_cost_basis(
                position=short_position,
                contracts=contracts,
            )
            total_entry_debit_dollars = long_cost - short_cost

            entry_debit_per_contract = None

            if total_entry_debit_dollars > 0:
                entry_debit_per_contract = (
                    total_entry_debit_dollars
                    / Decimal(contracts)
                    / Decimal("100")
                )
            elif entry_basis_by_structure is not None:
                recovered_basis = entry_basis_by_structure.get(
                    frozenset(
                        {
                            long_position.symbol,
                            short_position.symbol,
                        }
                    )
                )
                if recovered_basis is not None and recovered_basis > 0:
                    entry_debit_per_contract = recovered_basis

            if entry_debit_per_contract is not None:
                spreads.append(
                    ManagedBullCallSpread(
                        underlying=underlying,
                        expiration_code=expiration_code,
                        long_symbol=long_position.symbol,
                        short_symbol=short_position.symbol,
                        long_strike=long_strike,
                        short_strike=short_strike,
                        contracts=contracts,
                        entry_debit_per_contract=(
                            entry_debit_per_contract
                        ),
                        option_type=option_type,
                    )
                )

            long_remaining -= contracts
            short_remaining[short_index] -= contracts

    return tuple(spreads)


def _history_structure_spread(
    *,
    structure: frozenset[str],
    lots: tuple[Decimal, ...],
) -> ManagedBullCallSpread | None:
    if len(structure) != 2 or not lots:
        return None

    symbols = tuple(sorted(structure))
    parsed = tuple(
        _parse_option_contract(symbol)
        for symbol in symbols
    )
    if any(item is None for item in parsed):
        return None

    first = parsed[0]
    second = parsed[1]
    assert first is not None
    assert second is not None

    if (
        first[0] != second[0]
        or first[1] != second[1]
        or first[2] != second[2]
    ):
        return None

    underlying = first[0]
    expiration_code = first[1]
    option_type = first[2]

    by_strike = sorted(
        zip(symbols, parsed),
        key=lambda item: item[1][3],
    )
    lower_symbol, lower_parsed = by_strike[0]
    higher_symbol, higher_parsed = by_strike[1]

    if lower_parsed[3] == higher_parsed[3]:
        return None

    if option_type == "call":
        long_symbol = lower_symbol
        long_strike = lower_parsed[3]
        short_symbol = higher_symbol
        short_strike = higher_parsed[3]
    elif option_type == "put":
        long_symbol = higher_symbol
        long_strike = higher_parsed[3]
        short_symbol = lower_symbol
        short_strike = lower_parsed[3]
    else:
        return None

    entry_debit = (
        sum(lots, start=Decimal("0"))
        / Decimal(len(lots))
    )

    if entry_debit <= 0:
        return None

    return ManagedBullCallSpread(
        underlying=underlying,
        expiration_code=expiration_code,
        long_symbol=long_symbol,
        short_symbol=short_symbol,
        long_strike=long_strike,
        short_strike=short_strike,
        contracts=len(lots),
        entry_debit_per_contract=entry_debit,
        option_type=option_type,
    )


def identify_history_reconciled_debit_spreads(
    *,
    snapshot: PaperPortfolioSnapshot,
    recovery_result,
) -> HistoryReconciledSpreadState:
    """Use broker order history as spread identity and positions as proof.

    Historical MLEG lots define which exact verticals were actually opened.
    Current net positions are then compared against each disconnected history
    component. A component is manageable only when its signed symbol inventory
    matches exactly. This prevents nearest-strike reconstruction from pairing
    legs that originated in different spreads.
    """

    current_qty: dict[str, int] = {}

    for position in snapshot.positions:
        if _parse_option_contract(position.symbol) is None:
            continue

        quantity = position.qty
        if quantity == 0:
            continue
        if quantity != quantity.to_integral_value():
            # Non-integral option inventory cannot be reconciled safely.
            continue

        current_qty[position.symbol] = int(quantity)

    history_spreads = []

    for structure, lots in getattr(
        recovery_result,
        "open_lots_by_structure",
        {},
    ).items():
        spread = _history_structure_spread(
            structure=structure,
            lots=lots,
        )
        if spread is not None:
            history_spreads.append(spread)

    recovered_history_units = sum(
        spread.contracts
        for spread in history_spreads
    )

    # Build connected components by shared contract symbol. Exact historical
    # structures in separate components can be reconciled independently.
    symbol_to_indices: dict[str, set[int]] = {}

    for index, spread in enumerate(history_spreads):
        for symbol in (
            spread.long_symbol,
            spread.short_symbol,
        ):
            symbol_to_indices.setdefault(
                symbol,
                set(),
            ).add(index)

    remaining_indices = set(range(len(history_spreads)))
    components: list[set[int]] = []

    while remaining_indices:
        seed = remaining_indices.pop()
        component = {seed}
        queue = [seed]

        while queue:
            index = queue.pop()
            spread = history_spreads[index]

            for symbol in (
                spread.long_symbol,
                spread.short_symbol,
            ):
                for neighbor in symbol_to_indices.get(
                    symbol,
                    set(),
                ):
                    if neighbor in remaining_indices:
                        remaining_indices.remove(neighbor)
                        component.add(neighbor)
                        queue.append(neighbor)

        components.append(component)

    reconciled: list[ManagedBullCallSpread] = []
    covered_current_symbols: set[str] = set()
    unreconciled: set[str] = set()

    for component in components:
        predicted: dict[str, int] = {}
        component_symbols: set[str] = set()

        for index in component:
            spread = history_spreads[index]
            component_symbols.update(
                {
                    spread.long_symbol,
                    spread.short_symbol,
                }
            )
            predicted[spread.long_symbol] = (
                predicted.get(spread.long_symbol, 0)
                + spread.contracts
            )
            predicted[spread.short_symbol] = (
                predicted.get(spread.short_symbol, 0)
                - spread.contracts
            )

        matches_current_inventory = all(
            current_qty.get(symbol, 0)
            == predicted.get(symbol, 0)
            for symbol in component_symbols
        )

        if matches_current_inventory:
            for index in sorted(component):
                reconciled.append(
                    history_spreads[index]
                )
            covered_current_symbols.update(
                symbol
                for symbol in component_symbols
                if current_qty.get(symbol, 0) != 0
            )
            continue

        unreconciled.update(
            symbol
            for symbol in component_symbols
            if current_qty.get(symbol, 0) != 0
        )

    # Any current option inventory absent from surviving historical structures
    # is orphan inventory and must never be paired heuristically.
    historical_symbols = set(symbol_to_indices)

    unreconciled.update(
        symbol
        for symbol, quantity in current_qty.items()
        if (
            quantity != 0
            and symbol not in covered_current_symbols
            and (
                symbol not in historical_symbols
                or symbol in unreconciled
            )
        )
    )

    # A current symbol in a mismatched component is already included above.
    # Include any remaining non-covered current option symbols as a final
    # conservative guard.
    unreconciled.update(
        symbol
        for symbol, quantity in current_qty.items()
        if quantity != 0 and symbol not in covered_current_symbols
    )

    reconciled_units = sum(
        spread.contracts
        for spread in reconciled
    )

    return HistoryReconciledSpreadState(
        spreads=tuple(reconciled),
        unreconciled_option_symbols=tuple(
            sorted(unreconciled)
        ),
        recovered_history_units=(
            recovered_history_units
        ),
        reconciled_history_units=(
            reconciled_units
        ),
    )


def identify_managed_bull_call_spreads(
    snapshot: PaperPortfolioSnapshot,
) -> tuple[ManagedBullCallSpread, ...]:
    return tuple(
        spread
        for spread in identify_managed_debit_spreads(snapshot)
        if spread.option_type == "call"
    )


def _read_executable_close_credit(
    *,
    option_data_client,
    spread: ManagedBullCallSpread,
) -> Decimal:
    quotes = option_data_client.get_option_latest_quote(
        OptionLatestQuoteRequest(
            symbol_or_symbols=[
                spread.long_symbol,
                spread.short_symbol,
            ]
        )
    )

    long_quote = quotes.get(spread.long_symbol)
    short_quote = quotes.get(spread.short_symbol)

    if long_quote is None or short_quote is None:
        raise ValueError("spread_exit_quote_missing")

    long_bid = Decimal(str(long_quote.bid_price))
    short_ask = Decimal(str(short_quote.ask_price))

    if long_bid <= 0 or short_ask <= 0:
        raise ValueError("spread_exit_quote_invalid")

    close_credit = long_bid - short_ask

    if close_credit <= 0:
        raise ValueError("spread_exit_credit_non_positive")

    return close_credit.quantize(
        Decimal("0.01"),
        rounding=ROUND_DOWN,
    )


def _expected_return_percent(
    *,
    spread: ManagedBullCallSpread,
    close_credit: Decimal,
) -> Decimal:
    entry_debit = spread.entry_debit_per_contract

    if entry_debit <= 0:
        raise ValueError("spread_entry_debit_invalid")

    return (
        (close_credit - entry_debit)
        / entry_debit
        * Decimal("100")
    )


def _take_profit_limit_credit(
    *,
    spread: ManagedBullCallSpread,
    observed_close_credit: Decimal,
    take_profit_percent: Decimal,
    price_concession: Decimal,
) -> Decimal:
    if price_concession < 0:
        raise ValueError("take_profit_price_concession_must_be_non_negative")

    target_credit = (
        spread.entry_debit_per_contract
        * (
            Decimal("1")
            + take_profit_percent / Decimal("100")
        )
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_CEILING,
    )

    target_credit = min(target_credit, observed_close_credit)

    conceded_credit = (
        observed_close_credit - price_concession
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_CEILING,
    )

    return max(
        target_credit,
        conceded_credit,
        Decimal("0.01"),
    )


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _pending_exit_state(
    *,
    snapshot: PaperPortfolioSnapshot,
    timeout_seconds: int,
    now: datetime,
) -> tuple[tuple, tuple[frozenset[str], ...]]:
    stale_orders = []
    covered_structures: list[frozenset[str]] = []

    for order in getattr(
        snapshot,
        "pending_mleg_orders",
        (),
    ):
        if order.purpose != "exit":
            continue

        if order.symbols:
            covered_structures.append(
                frozenset(order.symbols)
            )

        if order.submitted_at is None:
            continue

        age_seconds = (
            _normalize_datetime(now)
            - _normalize_datetime(order.submitted_at)
        ).total_seconds()

        if age_seconds >= timeout_seconds:
            stale_orders.append(order)

    return tuple(stale_orders), tuple(covered_structures)


def _managed_contracts(spreads) -> int:
    return sum(
        spread.contracts
        for spread in spreads
    )


def _basis_recovery_diagnostic_lines(diagnostic) -> tuple[str, ...]:
    return (
        (
            "basis_recovery_closed_orders_returned="
            f"{diagnostic.closed_orders_returned}"
        ),
        (
            "basis_recovery_parsed_mleg_orders="
            f"{diagnostic.parsed_mleg_orders}"
        ),
        (
            "basis_recovery_entry_orders_recognized="
            f"{diagnostic.entry_orders_recognized}"
        ),
        (
            "basis_recovery_exit_orders_recognized="
            f"{diagnostic.exit_orders_recognized}"
        ),
        (
            "basis_recovery_missing_position_intent_orders="
            f"{diagnostic.missing_position_intent_orders}"
        ),
        (
            "basis_recovery_missing_filled_avg_price_entries="
            f"{diagnostic.missing_filled_avg_price_entries}"
        ),
        (
            "basis_recovery_missing_usable_price_entries="
            f"{diagnostic.missing_filled_price_entries}"
        ),
        (
            "basis_recovery_limit_price_fallback_entries="
            f"{diagnostic.limit_price_fallback_entries}"
        ),
        (
            "basis_recovery_fifo_underflow_structures="
            f"{diagnostic.fifo_underflow_structures}"
        ),
        (
            "basis_recovery_recovered_structures="
            f"{diagnostic.recovered_structures}"
        ),
    )


def _open_option_symbols(snapshot: PaperPortfolioSnapshot) -> tuple[str, ...]:
    return tuple(
        sorted(
            position.symbol
            for position in snapshot.positions
            if (
                position.qty != 0
                and _parse_option_contract(position.symbol) is not None
            )
        )
    )


def run_paper_spread_exit_cycle(
    *,
    trading_client,
    option_data_client,
    snapshot: PaperPortfolioSnapshot,
    take_profit_percent: Decimal = Decimal("10.00"),
    stop_loss_percent: Decimal = Decimal("50.00"),
    exit_order_timeout_seconds: int = 240,
    take_profit_price_concession: Decimal = Decimal("0.02"),
    entry_basis_provider=None,
    now_fn=None,
) -> PaperSpreadExitResult:
    if take_profit_percent < 0:
        raise ValueError(
            "take_profit_percent_must_be_non_negative"
        )

    if stop_loss_percent < 0:
        raise ValueError(
            "stop_loss_percent_must_be_non_negative"
        )

    if exit_order_timeout_seconds <= 0:
        raise ValueError(
            "exit_order_timeout_seconds_must_be_positive"
        )

    if take_profit_price_concession < 0:
        raise ValueError(
            "take_profit_price_concession_must_be_non_negative"
        )

    pending_orders = getattr(
        snapshot,
        "pending_mleg_orders",
        (),
    )

    if (
        not pending_orders
        and snapshot.pending_spread_units > 0
    ):
        return PaperSpreadExitResult(
            submitted=False,
            reason="pending_mleg_order_exists",
            block_new_entries=True,
        )

    if any(
        order.purpose == "unknown"
        for order in pending_orders
    ):
        return PaperSpreadExitResult(
            submitted=False,
            reason="pending_mleg_order_purpose_unknown",
            block_new_entries=True,
        )

    now = (
        now_fn()
        if now_fn is not None
        else datetime.now(timezone.utc)
    )
    stale_exit_orders, pending_exit_structures = (
        _pending_exit_state(
            snapshot=snapshot,
            timeout_seconds=exit_order_timeout_seconds,
            now=now,
        )
    )

    if stale_exit_orders:
        cancelled_ids = []

        for order in stale_exit_orders:
            if not order.order_id:
                return PaperSpreadExitResult(
                    submitted=False,
                    reason="stale_exit_order_id_missing",
                    block_new_entries=True,
                )

            trading_client.cancel_order_by_id(order.order_id)
            cancelled_ids.append(order.order_id)

        return PaperSpreadExitResult(
            submitted=False,
            reason="stale_exit_order_cancelled",
            block_new_entries=True,
            cancelled_order_ids=tuple(cancelled_ids),
        )

    spreads = identify_managed_debit_spreads(snapshot)
    expected_managed_units = int(snapshot.managed_spreads)

    if _managed_contracts(spreads) < expected_managed_units:
        recovery_diagnostics = ()

        if entry_basis_provider is None:
            from lockean_lite.filled_spread_basis import (
                recover_open_spread_entry_basis,
            )

            recovery_result = recover_open_spread_entry_basis(
                trading_client=trading_client
            )
            recovered_basis = recovery_result.basis_by_structure
            recovery_diagnostics = _basis_recovery_diagnostic_lines(
                recovery_result.diagnostics
            )
        else:
            recovered_basis = entry_basis_provider()

        spreads = identify_managed_debit_spreads(
            snapshot,
            entry_basis_by_structure=recovered_basis,
        )

        if _managed_contracts(spreads) < expected_managed_units:
            open_symbols = _open_option_symbols(snapshot)
            unresolved_line = (
                "unrecovered_open_symbols="
                + ",".join(open_symbols)
            )
            return PaperSpreadExitResult(
                submitted=False,
                reason="managed_spread_entry_basis_unavailable",
                block_new_entries=True,
                diagnostics=(
                    *recovery_diagnostics,
                    unresolved_line,
                ),
            )

    if not spreads:
        return PaperSpreadExitResult(
            submitted=False,
            reason="no_managed_spread_detected",
        )

    stop_candidates = []
    profit_candidates = []
    quote_failures = 0

    for spread in spreads:
        spread_structure = frozenset(
            {spread.long_symbol, spread.short_symbol}
        )

        if spread_structure in pending_exit_structures:
            continue

        try:
            close_credit = _read_executable_close_credit(
                option_data_client=option_data_client,
                spread=spread,
            )
        except ValueError:
            quote_failures += 1
            continue

        expected_return = _expected_return_percent(
            spread=spread,
            close_credit=close_credit,
        )

        candidate = (
            spread,
            close_credit,
            expected_return,
        )

        if expected_return <= -stop_loss_percent:
            stop_candidates.append(candidate)
        elif expected_return >= take_profit_percent:
            profit_candidates.append(candidate)

    selected = None
    reason = None

    if stop_candidates:
        selected = min(
            stop_candidates,
            key=lambda item: item[2],
        )
        reason = "stop_loss_exit_submitted"
    elif profit_candidates:
        selected = max(
            profit_candidates,
            key=lambda item: item[2],
        )
        reason = "take_profit_exit_submitted"

    if selected is None:
        if quote_failures:
            return PaperSpreadExitResult(
                submitted=False,
                reason="spread_exit_quote_unavailable",
                block_new_entries=True,
            )

        return PaperSpreadExitResult(
            submitted=False,
            reason=(
                "pending_exit_order_active"
                if pending_exit_structures
                else "no_managed_spread_exit_trigger"
            ),
            block_new_entries=False,
        )

    spread, close_credit, expected_return = selected

    if reason == "take_profit_exit_submitted":
        submitted_limit_credit = _take_profit_limit_credit(
            spread=spread,
            observed_close_credit=close_credit,
            take_profit_percent=take_profit_percent,
            price_concession=take_profit_price_concession,
        )
    else:
        submitted_limit_credit = close_credit

    submitted_limit_return = _expected_return_percent(
        spread=spread,
        close_credit=submitted_limit_credit,
    )

    order_request = build_managed_spread_close_order(
        long_symbol=spread.long_symbol,
        short_symbol=spread.short_symbol,
        contracts=spread.contracts,
        limit_credit=submitted_limit_credit,
    )

    broker_order = trading_client.submit_order(
        order_data=order_request,
    )

    broker_order_id = getattr(broker_order, "id", None)

    return PaperSpreadExitResult(
        submitted=True,
        reason=reason,
        broker_order_id=(
            str(broker_order_id)
            if broker_order_id is not None
            else None
        ),
        expected_return_percent=(
            expected_return.quantize(Decimal("0.01"))
        ),
        block_new_entries=False,
        observed_close_credit=close_credit,
        submitted_limit_credit=submitted_limit_credit,
        submitted_limit_return_percent=(
            submitted_limit_return.quantize(Decimal("0.01"))
        ),
        entry_debit_per_contract=spread.entry_debit_per_contract,
        contracts=spread.contracts,
        long_symbol=spread.long_symbol,
        short_symbol=spread.short_symbol,
    )
