import pytest
from lockean_lite.lockean_authority import LockeanAuthority
from lockean_lite.trade_proposal import TradeProposal
from datetime import date
from decimal import Decimal

from lockean_lite.option_leg import OptionLeg


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
        proposal_id="proposal-003",
        symbol="SPY",
        strategy="defined_risk_option",
        contracts=1,
        legs=(buy_leg, sell_leg),
        net_debit=Decimal("1.00"),
    )

    authority = LockeanAuthority()

    decision = authority.evaluate(proposal)

    assert decision.status == "REJECTED"
    assert decision.reason == "authorization_requirements_incomplete"
    assert decision.proposal_id == "proposal-003"


def test_authority_rejects_non_positive_contract_quantity():
    proposal = TradeProposal(
        proposal_id="proposal-004",
        symbol="SPY",
        strategy="defined_risk_option",
        contracts=0,
    )

    authority = LockeanAuthority()

    decision = authority.evaluate(proposal)

    assert decision.status == "REJECTED"
    assert decision.reason == "invalid_contract_quantity"
    assert decision.proposal_id == "proposal-004"


def test_authority_rejects_negative_contract_quantity():
    proposal = TradeProposal(
        proposal_id="proposal-005",
        symbol="SPY",
        strategy="defined_risk_option",
        contracts=-1,
    )

    authority = LockeanAuthority()

    decision = authority.evaluate(proposal)

    assert decision.status == "REJECTED"
    assert decision.reason == "invalid_contract_quantity"
    assert decision.proposal_id == "proposal-005"


def test_authority_decision_is_immutable_after_rejection():
    proposal = TradeProposal(
        proposal_id="proposal-006",
        symbol="SPY",
        strategy="unlimited_risk_option",
        contracts=1,
    )

    authority = LockeanAuthority()

    decision = authority.evaluate(proposal)

    with pytest.raises(AttributeError):
        decision.status = "AUTHORIZED"


def test_authority_rejects_defined_risk_proposal_without_exactly_two_legs():
    single_leg = OptionLeg(
        option_type="call",
        strike=Decimal("500"),
        expiration=date(2026, 9, 18),
        side="buy",
    )

    proposal = TradeProposal(
        proposal_id="proposal-008",
        symbol="SPY",
        strategy="defined_risk_option",
        contracts=1,
        legs=(single_leg,),
    )

    authority = LockeanAuthority()

    decision = authority.evaluate(proposal)

    assert decision.status == "REJECTED"
    assert decision.reason == "invalid_leg_count"
    assert decision.proposal_id == "proposal-008"

def test_authority_rejects_defined_risk_proposal_with_non_call_leg():
    buy_leg = OptionLeg(
        option_type="put",
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
        proposal_id="proposal-009",
        symbol="SPY",
        strategy="defined_risk_option",
        contracts=1,
        legs=(buy_leg, sell_leg),
    )

    authority = LockeanAuthority()

    decision = authority.evaluate(proposal)

    assert decision.status == "REJECTED"
    assert decision.reason == "unsupported_option_type"
    assert decision.proposal_id == "proposal-009"


def test_authority_rejects_defined_risk_proposal_without_one_buy_and_one_sell():
    first_leg = OptionLeg(
        option_type="call",
        strike=Decimal("500"),
        expiration=date(2026, 9, 18),
        side="buy",
    )

    second_leg = OptionLeg(
        option_type="call",
        strike=Decimal("505"),
        expiration=date(2026, 9, 18),
        side="buy",
    )

    proposal = TradeProposal(
        proposal_id="proposal-010",
        symbol="SPY",
        strategy="defined_risk_option",
        contracts=1,
        legs=(first_leg, second_leg),
    )

    authority = LockeanAuthority()

    decision = authority.evaluate(proposal)

    assert decision.status == "REJECTED"
    assert decision.reason == "invalid_leg_sides"
    assert decision.proposal_id == "proposal-010"


def test_authority_rejects_defined_risk_proposal_with_mismatched_expirations():
    buy_leg = OptionLeg(
        option_type="call",
        strike=Decimal("500"),
        expiration=date(2026, 9, 18),
        side="buy",
    )

    sell_leg = OptionLeg(
        option_type="call",
        strike=Decimal("505"),
        expiration=date(2026, 9, 25),
        side="sell",
    )

    proposal = TradeProposal(
        proposal_id="proposal-011",
        symbol="SPY",
        strategy="defined_risk_option",
        contracts=1,
        legs=(buy_leg, sell_leg),
    )

    authority = LockeanAuthority()

    decision = authority.evaluate(proposal)

    assert decision.status == "REJECTED"
    assert decision.reason == "expiration_mismatch"
    assert decision.proposal_id == "proposal-011"


def test_authority_rejects_defined_risk_proposal_with_invalid_strike_order():
    buy_leg = OptionLeg(
        option_type="call",
        strike=Decimal("505"),
        expiration=date(2026, 9, 18),
        side="buy",
    )

    sell_leg = OptionLeg(
        option_type="call",
        strike=Decimal("500"),
        expiration=date(2026, 9, 18),
        side="sell",
    )

    proposal = TradeProposal(
        proposal_id="proposal-012",
        symbol="SPY",
        strategy="defined_risk_option",
        contracts=1,
        legs=(buy_leg, sell_leg),
    )

    authority = LockeanAuthority()

    decision = authority.evaluate(proposal)

    assert decision.status == "REJECTED"
    assert decision.reason == "invalid_strike_order"
    assert decision.proposal_id == "proposal-012"


def test_authority_rejects_proposal_when_maximum_loss_exceeds_policy_limit():
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
        proposal_id="proposal-014",
        symbol="SPY",
        strategy="defined_risk_option",
        contracts=2,
        legs=(buy_leg, sell_leg),
        net_debit=Decimal("1.25"),
    )

    authority = LockeanAuthority(
        maximum_allowed_loss=Decimal("150.00"),
    )

    decision = authority.evaluate(proposal)

    assert decision.status == "REJECTED"
    assert decision.reason == "max_loss_exceeds_limit"
    assert decision.proposal_id == "proposal-014"

def test_authority_rejects_proposal_when_net_debit_is_missing():
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
        proposal_id="proposal-015",
        symbol="SPY",
        strategy="defined_risk_option",
        contracts=1,
        legs=(buy_leg, sell_leg),
        net_debit=None,

    )

    authority = LockeanAuthority(
        maximum_allowed_loss=Decimal("150.00"),
    )

    decision = authority.evaluate(proposal)

    assert decision.status == "REJECTED"
    assert decision.reason == "missing_net_debit"
    assert decision.proposal_id == "proposal-015"