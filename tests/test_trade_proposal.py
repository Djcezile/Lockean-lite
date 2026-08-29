import pytest

from lockean_lite.trade_proposal import TradeProposal


def test_trade_proposal_is_immutable_structured_intent():
    proposal = TradeProposal(
        proposal_id="proposal-001",
        symbol="SPY",
        strategy="defined_risk_option",
        contracts=1,
    )

    assert proposal.proposal_id == "proposal-001"
    assert proposal.symbol == "SPY"
    assert proposal.strategy == "defined_risk_option"
    assert proposal.contracts == 1

    with pytest.raises(AttributeError):
        proposal.contracts = 10