from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone

import pytest

from lockean_lite.authorization_receipt import (
    AuthorizationReceipt,
    ReceiptVerificationResult,
    issue_authorization_receipt,
    verify_authorization_receipt,
)


TEST_SIGNING_KEY = b"test-only-lockean-authority-key"

ISSUED_AT = datetime(
    2026,
    8,
    30,
    23,
    30,
    tzinfo=timezone.utc,
)

EXPIRES_AT = ISSUED_AT + timedelta(seconds=30)

PROPOSAL_FINGERPRINT = "proposal-fingerprint-abc123"


def _issue_receipt():
    return issue_authorization_receipt(
        receipt_id="receipt-001",
        proposal_fingerprint=PROPOSAL_FINGERPRINT,
        issued_at=ISSUED_AT,
        expires_at=EXPIRES_AT,
        signing_key=TEST_SIGNING_KEY,
    )


def test_authentic_authorization_receipt_is_immutable_and_verifies():
    receipt = _issue_receipt()

    assert isinstance(receipt, AuthorizationReceipt)
    assert receipt.receipt_id == "receipt-001"
    assert receipt.proposal_fingerprint == PROPOSAL_FINGERPRINT
    assert receipt.issued_at == ISSUED_AT
    assert receipt.expires_at == EXPIRES_AT
    assert receipt.authority_signature

    with pytest.raises(FrozenInstanceError):
        receipt.proposal_fingerprint = "changed"

    result = verify_authorization_receipt(
        receipt=receipt,
        signing_key=TEST_SIGNING_KEY,
        expected_proposal_fingerprint=PROPOSAL_FINGERPRINT,
        now=ISSUED_AT + timedelta(seconds=5),
    )

    assert result == ReceiptVerificationResult(
        valid=True,
        reason="receipt_valid",
    )


def test_receipt_issuance_rejects_invalid_expiration_window():
    with pytest.raises(
        ValueError,
        match="receipt_expiration_invalid",
    ):
        issue_authorization_receipt(
            receipt_id="receipt-002",
            proposal_fingerprint=PROPOSAL_FINGERPRINT,
            issued_at=ISSUED_AT,
            expires_at=ISSUED_AT,
            signing_key=TEST_SIGNING_KEY,
        )


def test_receipt_verification_rejects_wrong_authority_key():
    receipt = _issue_receipt()

    result = verify_authorization_receipt(
        receipt=receipt,
        signing_key=b"wrong-key",
        expected_proposal_fingerprint=PROPOSAL_FINGERPRINT,
        now=ISSUED_AT + timedelta(seconds=5),
    )

    assert result == ReceiptVerificationResult(
        valid=False,
        reason="invalid_authority_signature",
    )


def test_receipt_verification_rejects_tampered_signed_contents():
    receipt = _issue_receipt()

    tampered_receipt = replace(
        receipt,
        proposal_fingerprint="tampered-fingerprint",
    )

    result = verify_authorization_receipt(
        receipt=tampered_receipt,
        signing_key=TEST_SIGNING_KEY,
        expected_proposal_fingerprint="tampered-fingerprint",
        now=ISSUED_AT + timedelta(seconds=5),
    )

    assert result == ReceiptVerificationResult(
        valid=False,
        reason="invalid_authority_signature",
    )


def test_receipt_verification_rejects_receipt_for_different_proposal():
    receipt = _issue_receipt()

    result = verify_authorization_receipt(
        receipt=receipt,
        signing_key=TEST_SIGNING_KEY,
        expected_proposal_fingerprint="different-proposal-fingerprint",
        now=ISSUED_AT + timedelta(seconds=5),
    )

    assert result == ReceiptVerificationResult(
        valid=False,
        reason="receipt_proposal_mismatch",
    )


def test_receipt_verification_rejects_expired_receipt():
    receipt = _issue_receipt()

    result = verify_authorization_receipt(
        receipt=receipt,
        signing_key=TEST_SIGNING_KEY,
        expected_proposal_fingerprint=PROPOSAL_FINGERPRINT,
        now=EXPIRES_AT,
    )

    assert result == ReceiptVerificationResult(
        valid=False,
        reason="receipt_expired",
    )