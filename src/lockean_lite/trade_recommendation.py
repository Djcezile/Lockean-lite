from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from lockean_lite.option_leg import OptionLeg
from lockean_lite.option_quote_snapshot import (
    OptionQuoteSnapshot,
)
from lockean_lite.proposal_pricing import (
    build_quote_priced_trade_proposal,
)
from lockean_lite.trade_proposal import TradeProposal


@dataclass(frozen=True)
class SpreadRecommendation:
    proposal_id: str
    symbol: str
    expiration: date
    buy_strike: Decimal
    sell_strike: Decimal
    contracts: int


def _find_exact_quote(
    *,
    recommendation: SpreadRecommendation,
    strike: Decimal,
    candidate_quotes: tuple[
        OptionQuoteSnapshot,
        ...,
    ],
) -> OptionQuoteSnapshot:
    matches = tuple(
        quote
        for quote in candidate_quotes
        if (
            quote.underlying_symbol
            == recommendation.symbol
            and quote.option_type == "call"
            and quote.expiration
            == recommendation.expiration
            and quote.strike == strike
        )
    )

    if len(matches) != 1:
        raise ValueError(
            "recommended_option_quote_missing"
        )

    return matches[0]


def build_trade_proposal_from_recommendation(
    *,
    recommendation: SpreadRecommendation,
    candidate_quotes: tuple[
        OptionQuoteSnapshot,
        ...,
    ],
) -> TradeProposal:
    if recommendation.contracts <= 0:
        raise ValueError(
            "invalid_contract_quantity"
        )

    if (
        recommendation.buy_strike
        >= recommendation.sell_strike
    ):
        raise ValueError(
            "invalid_strike_order"
        )

    buy_quote = _find_exact_quote(
        recommendation=recommendation,
        strike=recommendation.buy_strike,
        candidate_quotes=candidate_quotes,
    )

    sell_quote = _find_exact_quote(
        recommendation=recommendation,
        strike=recommendation.sell_strike,
        candidate_quotes=candidate_quotes,
    )

    buy_leg = OptionLeg(
        option_type="call",
        strike=recommendation.buy_strike,
        expiration=recommendation.expiration,
        side="buy",
    )

    sell_leg = OptionLeg(
        option_type="call",
        strike=recommendation.sell_strike,
        expiration=recommendation.expiration,
        side="sell",
    )

    return build_quote_priced_trade_proposal(
        proposal_id=recommendation.proposal_id,
        symbol=recommendation.symbol,
        contracts=recommendation.contracts,
        buy_leg=buy_leg,
        sell_leg=sell_leg,
        buy_quote=buy_quote,
        sell_quote=sell_quote,
    )