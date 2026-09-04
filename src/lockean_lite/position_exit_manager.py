import re

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN

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


@dataclass(frozen=True)
class PaperSpreadExitResult:
    submitted: bool
    reason: str
    broker_order_id: str | None = None
    expected_return_percent: Decimal | None = None
    block_new_entries: bool = False


def _parse_call_contract(
    symbol: str,
) -> tuple[str, str, Decimal] | None:
    match = _OCC_CALL_PATTERN.fullmatch(
        symbol
    )

    if match is None:
        return None

    underlying = match.group(1)
    expiration_code = match.group(2)
    strike = (
        Decimal(match.group(3))
        / Decimal("1000")
    )

    return (
        underlying,
        expiration_code,
        strike,
    )


def identify_managed_bull_call_spreads(
    snapshot: PaperPortfolioSnapshot,
) -> tuple[ManagedBullCallSpread, ...]:
    long_positions: list[
        tuple[
            PaperPositionSnapshot,
            str,
            str,
            Decimal,
        ]
    ] = []
    short_positions: list[
        tuple[
            PaperPositionSnapshot,
            str,
            str,
            Decimal,
        ]
    ] = []

    for position in snapshot.positions:
        parsed = _parse_call_contract(
            position.symbol
        )

        if parsed is None:
            continue

        underlying, expiration_code, strike = (
            parsed
        )

        item = (
            position,
            underlying,
            expiration_code,
            strike,
        )

        if position.qty > 0:
            long_positions.append(item)
        elif position.qty < 0:
            short_positions.append(item)

    long_positions.sort(
        key=lambda item: (
            item[1],
            item[2],
            item[3],
        )
    )
    short_positions.sort(
        key=lambda item: (
            item[1],
            item[2],
            item[3],
        )
    )

    used_short_symbols: set[str] = set()
    spreads: list[ManagedBullCallSpread] = []

    for (
        long_position,
        underlying,
        expiration_code,
        long_strike,
    ) in long_positions:
        matches = [
            item
            for item in short_positions
            if (
                item[0].symbol
                not in used_short_symbols
                and item[1] == underlying
                and item[2] == expiration_code
                and item[3] > long_strike
                and abs(item[0].qty)
                == long_position.qty
            )
        ]

        if not matches:
            continue

        (
            short_position,
            _,
            _,
            short_strike,
        ) = min(
            matches,
            key=lambda item: item[3],
        )

        contracts_decimal = (
            long_position.qty
        )

        if (
            contracts_decimal
            != contracts_decimal.to_integral_value()
        ):
            continue

        contracts = int(
            contracts_decimal
        )

        if contracts <= 0:
            continue

        total_entry_debit_dollars = (
            abs(long_position.cost_basis)
            - abs(short_position.cost_basis)
        )

        if total_entry_debit_dollars <= 0:
            continue

        entry_debit_per_contract = (
            total_entry_debit_dollars
            / Decimal(contracts)
            / Decimal("100")
        )

        spreads.append(
            ManagedBullCallSpread(
                underlying=underlying,
                expiration_code=(
                    expiration_code
                ),
                long_symbol=(
                    long_position.symbol
                ),
                short_symbol=(
                    short_position.symbol
                ),
                long_strike=long_strike,
                short_strike=short_strike,
                contracts=contracts,
                entry_debit_per_contract=(
                    entry_debit_per_contract
                ),
            )
        )

        used_short_symbols.add(
            short_position.symbol
        )

    return tuple(spreads)


def _read_executable_close_credit(
    *,
    option_data_client,
    spread: ManagedBullCallSpread,
) -> Decimal:
    quotes = (
        option_data_client
        .get_option_latest_quote(
            OptionLatestQuoteRequest(
                symbol_or_symbols=[
                    spread.long_symbol,
                    spread.short_symbol,
                ]
            )
        )
    )

    long_quote = quotes.get(
        spread.long_symbol
    )
    short_quote = quotes.get(
        spread.short_symbol
    )

    if (
        long_quote is None
        or short_quote is None
    ):
        raise ValueError(
            "spread_exit_quote_missing"
        )

    long_bid = Decimal(
        str(long_quote.bid_price)
    )
    short_ask = Decimal(
        str(short_quote.ask_price)
    )

    if (
        long_bid <= 0
        or short_ask <= 0
    ):
        raise ValueError(
            "spread_exit_quote_invalid"
        )

    close_credit = (
        long_bid - short_ask
    )

    if close_credit <= 0:
        raise ValueError(
            "spread_exit_credit_non_positive"
        )

    return close_credit.quantize(
        Decimal("0.01"),
        rounding=ROUND_DOWN,
    )


def _expected_return_percent(
    *,
    spread: ManagedBullCallSpread,
    close_credit: Decimal,
) -> Decimal:
    entry_debit = (
        spread.entry_debit_per_contract
    )

    if entry_debit <= 0:
        raise ValueError(
            "spread_entry_debit_invalid"
        )

    return (
        (
            close_credit
            - entry_debit
        )
        / entry_debit
        * Decimal("100")
    )


def run_paper_spread_exit_cycle(
    *,
    trading_client,
    option_data_client,
    snapshot: PaperPortfolioSnapshot,
    take_profit_percent: Decimal = Decimal("10.00"),
    stop_loss_percent: Decimal = Decimal("50.00"),
) -> PaperSpreadExitResult:
    if take_profit_percent < 0:
        raise ValueError(
            "take_profit_percent_must_be_non_negative"
        )

    if stop_loss_percent < 0:
        raise ValueError(
            "stop_loss_percent_must_be_non_negative"
        )

    if snapshot.pending_spread_units > 0:
        return PaperSpreadExitResult(
            submitted=False,
            reason="pending_mleg_order_exists",
            block_new_entries=True,
        )

    spreads = (
        identify_managed_bull_call_spreads(
            snapshot
        )
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
        try:
            close_credit = (
                _read_executable_close_credit(
                    option_data_client=(
                        option_data_client
                    ),
                    spread=spread,
                )
            )
        except ValueError:
            quote_failures += 1
            continue

        expected_return = (
            _expected_return_percent(
                spread=spread,
                close_credit=close_credit,
            )
        )

        candidate = (
            spread,
            close_credit,
            expected_return,
        )

        if (
            expected_return
            <= -stop_loss_percent
        ):
            stop_candidates.append(
                candidate
            )
        elif (
            expected_return
            >= take_profit_percent
        ):
            profit_candidates.append(
                candidate
            )

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
            reason="no_managed_spread_exit_trigger",
        )

    (
        spread,
        close_credit,
        expected_return,
    ) = selected

    order_request = (
        build_managed_spread_close_order(
            long_symbol=spread.long_symbol,
            short_symbol=spread.short_symbol,
            contracts=spread.contracts,
            limit_credit=close_credit,
        )
    )

    broker_order = (
        trading_client.submit_order(
            order_data=order_request,
        )
    )

    broker_order_id = getattr(
        broker_order,
        "id",
        None,
    )

    return PaperSpreadExitResult(
        submitted=True,
        reason=reason,
        broker_order_id=(
            str(broker_order_id)
            if broker_order_id is not None
            else None
        ),
        expected_return_percent=(
            expected_return.quantize(
                Decimal("0.01")
            )
        ),
        block_new_entries=True,
    )
