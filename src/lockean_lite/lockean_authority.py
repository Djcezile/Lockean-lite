from dataclasses import dataclass

from lockean_lite.trade_proposal import TradeProposal


SUPPORTED_STRATEGIES = frozenset(
    {
        "defined_risk_option",
    }
)


@dataclass(frozen=True)
class AuthorityDecision:
    status: str
    reason: str
    proposal_id: str


class LockeanAuthority:
    def evaluate(self, proposal: TradeProposal) -> AuthorityDecision:
        if proposal.strategy not in SUPPORTED_STRATEGIES:
            return AuthorityDecision(
            status="REJECTED",
            reason="unsupported_strategy",
            proposal_id=proposal.proposal_id,
        )

        if proposal.contracts <= 0:
            return AuthorityDecision(
            status="REJECTED",
            reason="invalid_contract_quantity",
            proposal_id=proposal.proposal_id,
        )

        if len(proposal.legs) != 2:
            return AuthorityDecision(
            status="REJECTED",
            reason="invalid_leg_count",
            proposal_id=proposal.proposal_id,
        )

        if any(leg.option_type != "call" for leg in proposal.legs):
            return AuthorityDecision(
            status="REJECTED",
            reason="unsupported_option_type",
            proposal_id=proposal.proposal_id,
        )


        sides = {leg.side for leg in proposal.legs}

        if sides != {"buy", "sell"}:
            return AuthorityDecision(
            status="REJECTED",
            reason="invalid_leg_sides",
            proposal_id=proposal.proposal_id,
        )


        expirations = {leg.expiration for leg in proposal.legs}

        if len(expirations) != 1:
            return AuthorityDecision(
            status="REJECTED",
            reason="expiration_mismatch",
            proposal_id=proposal.proposal_id,
        )

        buy_leg = next(
        leg for leg in proposal.legs
        if leg.side == "buy"
    )

        sell_leg = next(
        leg for leg in proposal.legs
        if leg.side == "sell"
    )

        if buy_leg.strike >= sell_leg.strike:
            return AuthorityDecision(
            status="REJECTED",
            reason="invalid_strike_order",
            proposal_id=proposal.proposal_id,
        )

        return AuthorityDecision(
        status="REJECTED",
        reason="authorization_requirements_incomplete",
        proposal_id=proposal.proposal_id,
    )