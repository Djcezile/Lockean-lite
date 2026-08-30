from datetime import date
from decimal import Decimal

from lockean_lite.option_leg import OptionLeg
from lockean_lite.proposal_fingerprint import fingerprint_trade_proposal
from lockean_lite.trade_proposal import TradeProposal


def test_proposal_fingerprint_is_deterministic_for_same_financial_action():
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

    first = TradeProposal(
        proposal_id="proposal-018",
        symbol="SPY",
        strategy="defined_risk_option",
        contracts=1,
        legs=(buy_leg, sell_leg),
        net_debit=Decimal("1.00"),
    )

    reordered = TradeProposal(
        proposal_id="proposal-018",
        symbol="SPY",
        strategy="defined_risk_option",
        contracts=1,
        legs=(sell_leg, buy_leg),
        net_debit=Decimal("1.00"),
    )

    assert fingerprint_trade_proposal(first) == fingerprint_trade_proposal(
        reordered
    )

def test_proposal_fingerprint_changes_when_contract_quantity_changes():
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

    original = TradeProposal(
        proposal_id="proposal-019",
        symbol="SPY",
        strategy="defined_risk_option",
        contracts=1,
        legs=(buy_leg, sell_leg),
        net_debit=Decimal("1.00"),
    )

    tampered = TradeProposal(
        proposal_id="proposal-019",
        symbol="SPY",
        strategy="defined_risk_option",
        contracts=2,
        legs=(buy_leg, sell_leg),
        net_debit=Decimal("1.00"),
    )

    assert fingerprint_trade_proposal(
        original
    ) != fingerprint_trade_proposal(
        tampered
    )