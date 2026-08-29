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

        return AuthorityDecision(
        status="REJECTED",
        reason="authorization_requirements_incomplete",
        proposal_id=proposal.proposal_id,
    )