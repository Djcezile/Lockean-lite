from decimal import Decimal

from lockean_lite.option_leg import OptionLeg
from lockean_lite.option_quote_snapshot import (
    OptionQuoteSnapshot,
)
from lockean_lite.trade_proposal import TradeProposal


def _quote_matches_leg(
    *,
    symbol: str,
    leg: OptionLeg,
    quote: OptionQuoteSnapshot,
) -> bool:
    return (
        quote.source == "alpaca"
        and quote.underlying_symbol == symbol
        and quote.option_type == leg.option_type
        and quote.strike == leg.strike
        and quote.expiration == leg.expiration
    )


def derive_bull_call_spread_limit_debit(
    *,
    symbol: str,
    buy_leg: OptionLeg,
    sell_leg: OptionLeg,
    buy_quote: OptionQuoteSnapshot,
    sell_quote: OptionQuoteSnapshot,
) -> Decimal:
    if (
        buy_leg.side != "buy"
        or sell_leg.side != "sell"
    ):
        raise ValueError(
            "invalid_leg_sides"
        )

    if (
        not _quote_matches_leg(
            symbol=symbol,
            leg=buy_leg,
            quote=buy_quote,
        )
        or not _quote_matches_leg(
            symbol=symbol,
            leg=sell_leg,
            quote=sell_quote,
        )
    ):
        raise ValueError(
            "option_quote_leg_mismatch"
        )

    net_debit = (
        buy_quote.ask_price
        - sell_quote.bid_price
    )

    if net_debit <= 0:
        raise ValueError(
            "invalid_derived_net_debit"
        )

    return net_debit


def build_quote_priced_trade_proposal(
    *,
    proposal_id: str,
    symbol: str,
    contracts: int,
    buy_leg: OptionLeg,
    sell_leg: OptionLeg,
    buy_quote: OptionQuoteSnapshot,
    sell_quote: OptionQuoteSnapshot,
) -> TradeProposal:
    net_debit = derive_bull_call_spread_limit_debit(
        symbol=symbol,
        buy_leg=buy_leg,
        sell_leg=sell_leg,
        buy_quote=buy_quote,
        sell_quote=sell_quote,
    )

    return TradeProposal(
        proposal_id=proposal_id,
        symbol=symbol,
        strategy="defined_risk_option",
        contracts=contracts,
        legs=(
            buy_leg,
            sell_leg,
        ),
        net_debit=net_debit,
    )