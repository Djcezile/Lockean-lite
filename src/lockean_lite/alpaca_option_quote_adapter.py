from datetime import date
from decimal import Decimal

from alpaca.data.requests import (
    OptionLatestQuoteRequest,
)
from alpaca.trading.enums import ContractType
from alpaca.trading.requests import (
    GetOptionContractsRequest,
)

from lockean_lite.option_quote_snapshot import (
    OptionQuoteSnapshot,
)


def _decimal_string(
    value: Decimal,
) -> str:
    return format(
        value.normalize(),
        "f",
    )


def _option_type_text(contract_type) -> str:
    if contract_type == ContractType.CALL:
        return "call"
    if contract_type == ContractType.PUT:
        return "put"
    raise ValueError(
        "unsupported_option_type"
    )


def _translate_alpaca_option_quote(
    *,
    contract,
    quote,
    allowed_types,
) -> OptionQuoteSnapshot:
    if not contract.tradable:
        raise ValueError(
            "option_contract_not_tradable"
        )

    if contract.type not in allowed_types:
        raise ValueError(
            "unsupported_option_type"
        )

    bid_price = Decimal(
        str(quote.bid_price)
    )

    ask_price = Decimal(
        str(quote.ask_price)
    )

    if (
        bid_price < 0
        or ask_price <= 0
        or bid_price > ask_price
    ):
        raise ValueError(
            "invalid_option_quote"
        )

    return OptionQuoteSnapshot(
        contract_symbol=contract.symbol,
        underlying_symbol=(
            contract.underlying_symbol
        ),
        option_type=_option_type_text(
            contract.type
        ),
        strike=Decimal(
            str(contract.strike_price)
        ),
        expiration=(
            contract.expiration_date
        ),
        bid_price=bid_price,
        ask_price=ask_price,
        quote_timestamp=(
            quote.timestamp
        ),
        source="alpaca",
    )


def translate_alpaca_option_quote(
    *,
    contract,
    quote,
) -> OptionQuoteSnapshot:
    # Preserve the original call-only public contract for existing callers.
    return _translate_alpaca_option_quote(
        contract=contract,
        quote=quote,
        allowed_types={ContractType.CALL},
    )


def translate_alpaca_directional_option_quote(
    *,
    contract,
    quote,
) -> OptionQuoteSnapshot:
    return _translate_alpaca_option_quote(
        contract=contract,
        quote=quote,
        allowed_types={
            ContractType.CALL,
            ContractType.PUT,
        },
    )


def _read_spy_candidate_quotes(
    *,
    trading_client,
    option_data_client,
    expiration: date,
    minimum_strike: Decimal,
    maximum_strike: Decimal,
    contract_type,
) -> tuple[OptionQuoteSnapshot, ...]:
    response = (
        trading_client.get_option_contracts(
            GetOptionContractsRequest(
                underlying_symbols=["SPY"],
                expiration_date=expiration,
                type=contract_type,
                strike_price_gte=(
                    _decimal_string(
                        minimum_strike
                    )
                ),
                strike_price_lte=(
                    _decimal_string(
                        maximum_strike
                    )
                ),
                limit=100,
            )
        )
    )

    contracts = tuple(
        contract
        for contract in (
            response.option_contracts
            or []
        )
        if contract.tradable
    )

    if not contracts:
        return ()

    symbols = tuple(
        contract.symbol
        for contract in contracts
    )

    quotes = (
        option_data_client
        .get_option_latest_quote(
            OptionLatestQuoteRequest(
                symbol_or_symbols=list(
                    symbols
                ),
            )
        )
    )

    snapshots = []

    for contract in contracts:
        quote = quotes.get(
            contract.symbol
        )

        if quote is None:
            continue

        try:
            snapshot = (
                translate_alpaca_directional_option_quote(
                    contract=contract,
                    quote=quote,
                )
            )
        except ValueError:
            continue

        snapshots.append(
            snapshot
        )

    return tuple(snapshots)


def read_spy_call_candidate_quotes(
    *,
    trading_client,
    option_data_client,
    expiration: date,
    minimum_strike: Decimal,
    maximum_strike: Decimal,
) -> tuple[OptionQuoteSnapshot, ...]:
    snapshots = _read_spy_candidate_quotes(
        trading_client=trading_client,
        option_data_client=option_data_client,
        expiration=expiration,
        minimum_strike=minimum_strike,
        maximum_strike=maximum_strike,
        contract_type=ContractType.CALL,
    )

    if not snapshots:
        raise ValueError(
            "option_candidate_universe_empty"
        )

    return tuple(
        sorted(
            snapshots,
            key=lambda snapshot: (
                snapshot.strike,
                snapshot.contract_symbol,
            ),
        )
    )


def read_spy_directional_candidate_quotes(
    *,
    trading_client,
    option_data_client,
    expiration: date,
    minimum_strike: Decimal,
    maximum_strike: Decimal,
) -> tuple[OptionQuoteSnapshot, ...]:
    snapshots = (
        _read_spy_candidate_quotes(
            trading_client=trading_client,
            option_data_client=option_data_client,
            expiration=expiration,
            minimum_strike=minimum_strike,
            maximum_strike=maximum_strike,
            contract_type=ContractType.CALL,
        )
        + _read_spy_candidate_quotes(
            trading_client=trading_client,
            option_data_client=option_data_client,
            expiration=expiration,
            minimum_strike=minimum_strike,
            maximum_strike=maximum_strike,
            contract_type=ContractType.PUT,
        )
    )

    if not snapshots:
        raise ValueError(
            "option_candidate_universe_empty"
        )

    return tuple(
        sorted(
            snapshots,
            key=lambda snapshot: (
                snapshot.option_type,
                snapshot.strike,
                snapshot.contract_symbol,
            ),
        )
    )
