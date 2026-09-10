from dataclasses import dataclass

from lockean_lite.position_exit_manager import (
    identify_managed_bull_call_spreads,
)


@dataclass(frozen=True)
class EntryProposalPolicyDecision:
    allowed: bool
    reason: str


def _matching_contract_symbol(*, proposal, leg, candidate_quotes):
    matches = tuple(
        quote.contract_symbol
        for quote in candidate_quotes
        if (
            quote.underlying_symbol == proposal.symbol
            and quote.option_type == leg.option_type
            and quote.expiration == leg.expiration
            and quote.strike == leg.strike
        )
    )

    if len(matches) != 1:
        return None

    return matches[0]


def evaluate_entry_proposal_policy(
    *,
    proposal,
    candidate_quotes,
    snapshot,
    maximum_same_structure_units: int = 2,
) -> EntryProposalPolicyDecision:
    """Fail closed on portfolio conflicts before broker submission.

    This is an additional pre-authority portfolio guard. It does not grant
    permission; a passing proposal must still clear evidence validation,
    Lockean Authority, receipt verification, and the Execution Gateway.
    """
    if maximum_same_structure_units <= 0:
        raise ValueError("maximum_same_structure_units_must_be_positive")

    if len(proposal.legs) != 2:
        return EntryProposalPolicyDecision(
            allowed=False,
            reason="entry_proposal_leg_count_invalid",
        )

    buy_legs = tuple(leg for leg in proposal.legs if leg.side == "buy")
    sell_legs = tuple(leg for leg in proposal.legs if leg.side == "sell")

    if len(buy_legs) != 1 or len(sell_legs) != 1:
        return EntryProposalPolicyDecision(
            allowed=False,
            reason="entry_proposal_leg_sides_invalid",
        )

    buy_leg = buy_legs[0]
    sell_leg = sell_legs[0]

    buy_symbol = _matching_contract_symbol(
        proposal=proposal,
        leg=buy_leg,
        candidate_quotes=candidate_quotes,
    )
    sell_symbol = _matching_contract_symbol(
        proposal=proposal,
        leg=sell_leg,
        candidate_quotes=candidate_quotes,
    )

    if buy_symbol is None or sell_symbol is None:
        return EntryProposalPolicyDecision(
            allowed=False,
            reason="entry_contract_resolution_ambiguous",
        )

    proposal_symbols = {buy_symbol, sell_symbol}

    for order in getattr(snapshot, "pending_mleg_orders", ()):
        if not proposal_symbols.intersection(order.symbols):
            continue

        if order.purpose == "exit":
            reason = "entry_conflicts_with_pending_exit_order"
        elif order.purpose == "entry":
            reason = "entry_conflicts_with_pending_entry_order"
        else:
            reason = "entry_conflicts_with_unknown_pending_order"

        return EntryProposalPolicyDecision(
            allowed=False,
            reason=reason,
        )

    positions_by_symbol = {
        position.symbol: position
        for position in snapshot.positions
    }

    buy_position = positions_by_symbol.get(buy_symbol)
    if buy_position is not None and buy_position.qty < 0:
        return EntryProposalPolicyDecision(
            allowed=False,
            reason="buy_to_open_conflicts_with_short_position",
        )

    sell_position = positions_by_symbol.get(sell_symbol)
    if sell_position is not None and sell_position.qty > 0:
        return EntryProposalPolicyDecision(
            allowed=False,
            reason="sell_to_open_conflicts_with_long_position",
        )

    expiration_code = buy_leg.expiration.strftime("%y%m%d")
    same_structure_units = sum(
        spread.contracts
        for spread in identify_managed_bull_call_spreads(snapshot)
        if (
            spread.underlying == proposal.symbol
            and spread.expiration_code == expiration_code
            and spread.long_strike == buy_leg.strike
            and spread.short_strike == sell_leg.strike
        )
    )

    if same_structure_units >= maximum_same_structure_units:
        return EntryProposalPolicyDecision(
            allowed=False,
            reason="same_structure_concentration_limit_reached",
        )

    return EntryProposalPolicyDecision(
        allowed=True,
        reason="entry_portfolio_policy_passed",
    )
