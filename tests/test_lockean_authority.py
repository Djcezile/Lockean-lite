from lockean_lite.lockean_authority import LockeanAuthority
from lockean_lite.trade_proposal import TradeProposal


def test_authority_rejects_unsupported_strategy():
    proposal = TradeProposal(
        proposal_id="proposal-002",
        symbol="SPY",
        strategy="unlimited_risk_option",
        contracts=1,
    )

    authority = LockeanAuthority()

    decision = authority.evaluate(proposal)

    assert decision.status == "REJECTED"
    assert decision.reason == "unsupported_strategy"
    assert decision.proposal_id == "proposal-002"


def test_authority_rejects_supported_strategy_when_authorization_requirements_are_incomplete():
    proposal = TradeProposal(
        proposal_id="proposal-003",
        symbol="SPY",
        strategy="defined_risk_option",
        contracts=1,
    )

    authority = LockeanAuthority()

    decision = authority.evaluate(proposal)

    assert decision.status == "REJECTED"
    assert decision.reason == "authorization_requirements_incomplete"
    assert decision.proposal_id == "proposal-003"