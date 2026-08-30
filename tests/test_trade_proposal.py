import pytest

from lockean_lite.trade_proposal import TradeProposal
from datetime import date
from decimal import Decimal

from lockean_lite.option_leg import OptionLeg


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


def test_trade_proposal_preserves_exact_option_legs():
    buy_leg = OptionLeg(
        option_type="call",
        strike=Decimal("500"),
        expiration=date(2026, 9, 18),
        side="buy",
    )

    sell_leg = OptionLeg(
        option_type="call",
        strike=Decimal("505"),
        expiration=date(2026, 9, 18),
        side="sell",
    )

    proposal = TradeProposal(
        proposal_id="proposal-007",
        symbol="SPY",
        strategy="defined_risk_option",
        contracts=1,
        legs=(buy_leg, sell_leg),
    )

    assert proposal.legs == (buy_leg, sell_leg)