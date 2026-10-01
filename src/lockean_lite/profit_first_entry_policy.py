from dataclasses import dataclass
from decimal import Decimal

from lockean_lite.trade_proposal import TradeProposal


MINIMUM_REWARD_TO_RISK = Decimal("1.50")
ESTIMATED_ROUND_TRIP_COST_PER_CONTRACT = Decimal("0.10")
_CONTRACT_MULTIPLIER = Decimal("100")


@dataclass(frozen=True)
class ProfitFirstEntryDecision:
    allowed: bool
    reason: str
    reward_to_risk: Decimal | None = None


def _decision(
    *,
    allowed: bool,
    reason: str,
    reward_to_risk: Decimal | None = None,
) -> ProfitFirstEntryDecision:
    return ProfitFirstEntryDecision(
        allowed=allowed,
        reason=reason,
        reward_to_risk=reward_to_risk,
    )


def evaluate_profit_first_market_context(
    *,
    market_context: dict[str, str],
) -> ProfitFirstEntryDecision:
    """Reject an ineligible market before option discovery or AI inference."""
    for signal in (
        "trend",
        "momentum",
        "breakout",
        "volatility",
    ):
        if market_context.get(signal) != "PASS":
            return _decision(
                allowed=False,
                reason=f"profit_first_{signal}_not_confirmed",
            )

    if market_context.get("intraday_status") != "AVAILABLE":
        return _decision(
            allowed=False,
            reason="profit_first_intraday_not_ready",
        )

    if any(
        market_context.get(key) != "UP"
        for key in (
            "spy_session_direction",
            "intraday_direction_15m",
            "intraday_direction_30m",
        )
    ):
        return _decision(
            allowed=False,
            reason="profit_first_intraday_alignment_missing",
        )

    return _decision(
        allowed=True,
        reason="profit_first_market_context_eligible",
    )


def _bull_call_legs(proposal: TradeProposal):
    if len(proposal.legs) != 2:
        return None

    buy_legs = tuple(
        leg for leg in proposal.legs if leg.side == "buy"
    )
    sell_legs = tuple(
        leg for leg in proposal.legs if leg.side == "sell"
    )

    if len(buy_legs) != 1 or len(sell_legs) != 1:
        return None

    buy_leg = buy_legs[0]
    sell_leg = sell_legs[0]

    if (
        buy_leg.option_type != "call"
        or sell_leg.option_type != "call"
        or buy_leg.strike >= sell_leg.strike
    ):
        return None

    return buy_leg, sell_leg


def _reward_to_risk(
    *,
    proposal: TradeProposal,
    buy_strike: Decimal,
    sell_strike: Decimal,
    estimated_round_trip_cost_per_contract: Decimal,
) -> Decimal | None:
    if proposal.net_debit is None or proposal.net_debit <= 0:
        return None

    width = sell_strike - buy_strike
    if width <= proposal.net_debit:
        return Decimal("0")

    contracts = Decimal(proposal.contracts)
    estimated_cost = (
        estimated_round_trip_cost_per_contract * contracts
    )
    maximum_loss = (
        proposal.net_debit * _CONTRACT_MULTIPLIER * contracts
    ) + estimated_cost
    maximum_reward = (
        (width - proposal.net_debit)
        * _CONTRACT_MULTIPLIER
        * contracts
    ) - estimated_cost

    if maximum_loss <= 0 or maximum_reward <= 0:
        return Decimal("0")

    return (maximum_reward / maximum_loss).quantize(
        Decimal("0.001")
    )


def evaluate_profit_first_entry(
    *,
    proposal: TradeProposal,
    market_context: dict[str, str],
    minimum_reward_to_risk: Decimal = MINIMUM_REWARD_TO_RISK,
    estimated_round_trip_cost_per_contract: Decimal = (
        ESTIMATED_ROUND_TRIP_COST_PER_CONTRACT
    ),
) -> ProfitFirstEntryDecision:
    """Evaluate the first explicitly testable profit-seeking hypothesis.

    The current validated hypothesis is deliberately narrow: one SPY bull-call
    debit spread may proceed only when completed-session trend, momentum,
    breakout, and volatility filters agree; session, 15-minute, and 30-minute
    directions are all up; and trusted quote economics retain at least the
    configured reward-to-risk ratio after estimated round-trip costs.

    This gate does not assert profitability and cannot authorize execution. A
    passing proposal must still clear portfolio policy, Lockean Authority, and
    the Execution Gateway.
    """
    if minimum_reward_to_risk <= 0:
        raise ValueError(
            "minimum_reward_to_risk_must_be_positive"
        )
    if estimated_round_trip_cost_per_contract < 0:
        raise ValueError(
            "estimated_round_trip_cost_must_be_non_negative"
        )
    if proposal.contracts <= 0:
        return _decision(
            allowed=False,
            reason="profit_first_contract_quantity_invalid",
        )

    legs = _bull_call_legs(proposal)
    if legs is None:
        return _decision(
            allowed=False,
            reason="profit_first_strategy_not_validated",
        )

    if proposal.net_debit is None or proposal.net_debit <= 0:
        return _decision(
            allowed=False,
            reason="profit_first_pricing_missing",
        )

    buy_leg, sell_leg = legs
    reward_to_risk = _reward_to_risk(
        proposal=proposal,
        buy_strike=buy_leg.strike,
        sell_strike=sell_leg.strike,
        estimated_round_trip_cost_per_contract=(
            estimated_round_trip_cost_per_contract
        ),
    )

    if (
        reward_to_risk is None
        or reward_to_risk < minimum_reward_to_risk
    ):
        return _decision(
            allowed=False,
            reason="profit_first_reward_to_risk_below_minimum",
            reward_to_risk=reward_to_risk,
        )

    market_decision = evaluate_profit_first_market_context(
        market_context=market_context,
    )
    if not market_decision.allowed:
        return _decision(
            allowed=False,
            reason=market_decision.reason,
            reward_to_risk=reward_to_risk,
        )

    return _decision(
        allowed=True,
        reason="profit_first_entry_eligible",
        reward_to_risk=reward_to_risk,
    )
