from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from lockean_lite.authorization_receipt import (
    issue_authorization_receipt,
)
from lockean_lite.execution_gateway import (
    validate_execution_authority,
)
from lockean_lite.option_leg import OptionLeg
from lockean_lite.proposal_fingerprint import (
    fingerprint_trade_proposal,
)
from lockean_lite.trade_proposal import TradeProposal


TEST_SIGNING_KEY = b"test-only-execution-gateway-key"

NOW = datetime(
    2026,
    8,
    31,
    0,
    45,
    tzinfo=timezone.utc,
)


def _proposal(contracts=1):
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

    return TradeProposal(
        proposal_id="proposal-029",
        symbol="SPY",
        strategy="defined_risk_option",
        contracts=contracts,
        legs=(buy_leg, sell_leg),
        net_debit=Decimal("1.00"),
    )


def _receipt_for(proposal):
    return issue_authorization_receipt(
        receipt_id="receipt-gateway-001",
        proposal_fingerprint=fingerprint_trade_proposal(
            proposal
        ),
        issued_at=NOW,
        expires_at=NOW + timedelta(seconds=30),
        signing_key=TEST_SIGNING_KEY,
    )


def test_execution_gateway_rejects_missing_receipt():
    decision = validate_execution_authority(
        proposal=_proposal(),
        receipt=None,
        signing_key=TEST_SIGNING_KEY,
        now=NOW,
    )

    assert decision.allowed is False
    assert decision.reason == "authorization_receipt_required"


def test_execution_gateway_rejects_forged_receipt():
    proposal = _proposal()
    receipt = _receipt_for(proposal)

    forged = replace(
        receipt,
        authority_signature="not-a-valid-signature",
    )

    decision = validate_execution_authority(
        proposal=proposal,
        receipt=forged,
        signing_key=TEST_SIGNING_KEY,
        now=NOW + timedelta(seconds=5),
    )

    assert decision.allowed is False
    assert decision.reason == "invalid_authority_signature"


def test_execution_gateway_rejects_expired_receipt():
    proposal = _proposal()

    decision = validate_execution_authority(
        proposal=proposal,
        receipt=_receipt_for(proposal),
        signing_key=TEST_SIGNING_KEY,
        now=NOW + timedelta(seconds=30),
    )

    assert decision.allowed is False
    assert decision.reason == "receipt_expired"


def test_execution_gateway_rejects_tampered_proposal():
    original = _proposal(contracts=1)
    receipt = _receipt_for(original)

    tampered = _proposal(contracts=2)

    decision = validate_execution_authority(
        proposal=tampered,
        receipt=receipt,
        signing_key=TEST_SIGNING_KEY,
        now=NOW + timedelta(seconds=5),
    )

    assert decision.allowed is False
    assert decision.reason == "receipt_proposal_mismatch"


def test_execution_gateway_allows_exact_authorized_proposal():
    proposal = _proposal()

    decision = validate_execution_authority(
        proposal=proposal,
        receipt=_receipt_for(proposal),
        signing_key=TEST_SIGNING_KEY,
        now=NOW + timedelta(seconds=5),
    )

    assert decision.allowed is True
    assert decision.reason == "execution_authority_valid"