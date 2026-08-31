from decimal import Decimal

from alpaca.trading.enums import (
    ContractType,
    OrderClass,
    OrderSide,
    PositionIntent,
    TimeInForce,
)
from alpaca.trading.requests import (
    GetOptionContractsRequest,
    LimitOrderRequest,
    OptionLegRequest,
)

from lockean_lite.trade_proposal import TradeProposal


def _decimal_string(value: Decimal) -> str:
    return format(value.normalize(), "f")


def resolve_option_contract_symbols(
    *,
    client,
    proposal: TradeProposal,
) -> tuple[str, ...]:
    resolved_symbols = []

    for leg in proposal.legs:
        if leg.option_type != "call":
            raise ValueError("unsupported_option_type")

        strike = _decimal_string(leg.strike)

        request = GetOptionContractsRequest(
            underlying_symbols=[proposal.symbol],
            expiration_date=leg.expiration,
            type=ContractType.CALL,
            strike_price_gte=strike,
            strike_price_lte=strike,
            limit=10,
        )

        response = client.get_option_contracts(request)

        contracts = (
            response.option_contracts
            if response.option_contracts is not None
            else []
        )

        exact_matches = [
            contract
            for contract in contracts
            if (
                contract.tradable
                and contract.underlying_symbol
                == proposal.symbol
                and contract.expiration_date
                == leg.expiration
                and contract.type
                == ContractType.CALL
                and Decimal(str(contract.strike_price))
                == leg.strike
            )
        ]

        if not exact_matches:
            raise ValueError(
                "option_contract_not_found"
            )

        if len(exact_matches) != 1:
            raise ValueError(
                "option_contract_ambiguous"
            )

        resolved_symbols.append(
            exact_matches[0].symbol
        )

    return tuple(resolved_symbols)


def build_authorized_mleg_limit_order(
    *,
    proposal: TradeProposal,
    contract_symbols: tuple[str, ...],
) -> LimitOrderRequest:
    if len(contract_symbols) != len(proposal.legs):
        raise ValueError(
            "resolved_contract_count_mismatch"
        )

    option_legs = []

    for leg, contract_symbol in zip(
        proposal.legs,
        contract_symbols,
    ):
        if leg.side == "buy":
            side = OrderSide.BUY
            position_intent = (
                PositionIntent.BUY_TO_OPEN
            )
        elif leg.side == "sell":
            side = OrderSide.SELL
            position_intent = (
                PositionIntent.SELL_TO_OPEN
            )
        else:
            raise ValueError(
                "invalid_leg_side"
            )

        option_legs.append(
            OptionLegRequest(
                symbol=contract_symbol,
                ratio_qty=1,
                side=side,
                position_intent=position_intent,
            )
        )

    return LimitOrderRequest(
        qty=proposal.contracts,
        limit_price=float(proposal.net_debit),
        time_in_force=TimeInForce.DAY,
        order_class=OrderClass.MLEG,
        legs=option_legs,
    )