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


def translate_alpaca_option_quote(
    *,
    contract,
    quote,
) -> OptionQuoteSnapshot:
    if not contract.tradable:
        raise ValueError(
            "option_contract_not_tradable"
        )

    if contract.type != ContractType.CALL:
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
        option_type="call",
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


def read_spy_call_candidate_quotes(
    *,
    trading_client,
    option_data_client,
    expiration: date,
    minimum_strike: Decimal,
    maximum_strike: Decimal,
) -> tuple[OptionQuoteSnapshot, ...]:
    response = (
        trading_client.get_option_contracts(
            GetOptionContractsRequest(
                underlying_symbols=["SPY"],
                expiration_date=expiration,
                type=ContractType.CALL,
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
        raise ValueError(
            "option_candidate_universe_empty"
        )

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
                translate_alpaca_option_quote(
                    contract=contract,
                    quote=quote,
                )
            )
        except ValueError:
            continue

        snapshots.append(
            snapshot
        )

    snapshots.sort(
        key=lambda snapshot: (
            snapshot.strike,
            snapshot.contract_symbol,
        )
    )

    if not snapshots:
        raise ValueError(
            "option_candidate_universe_empty"
        )

    return tuple(
        snapshots
    )