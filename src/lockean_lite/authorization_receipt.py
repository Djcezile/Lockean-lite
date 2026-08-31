import hashlib
import hmac
import json

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class AuthorizationReceipt:
    receipt_id: str
    proposal_fingerprint: str
    issued_at: datetime
    expires_at: datetime
    authority_signature: str


@dataclass(frozen=True)
class ReceiptVerificationResult:
    valid: bool
    reason: str


def _canonical_receipt_payload(
    receipt_id: str,
    proposal_fingerprint: str,
    issued_at: datetime,
    expires_at: datetime,
) -> bytes:
    payload = {
        "expires_at": expires_at.isoformat(),
        "issued_at": issued_at.isoformat(),
        "proposal_fingerprint": proposal_fingerprint,
        "receipt_id": receipt_id,
    }

    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _calculate_authority_signature(
    *,
    receipt_id: str,
    proposal_fingerprint: str,
    issued_at: datetime,
    expires_at: datetime,
    signing_key: bytes,
) -> str:
    payload = _canonical_receipt_payload(
        receipt_id=receipt_id,
        proposal_fingerprint=proposal_fingerprint,
        issued_at=issued_at,
        expires_at=expires_at,
    )

    return hmac.new(
        signing_key,
        payload,
        hashlib.sha256,
    ).hexdigest()


def issue_authorization_receipt(
    *,
    receipt_id: str,
    proposal_fingerprint: str,
    issued_at: datetime,
    expires_at: datetime,
    signing_key: bytes,
) -> AuthorizationReceipt:
    if expires_at <= issued_at:
        raise ValueError("receipt_expiration_invalid")

    authority_signature = _calculate_authority_signature(
        receipt_id=receipt_id,
        proposal_fingerprint=proposal_fingerprint,
        issued_at=issued_at,
        expires_at=expires_at,
        signing_key=signing_key,
    )

    return AuthorizationReceipt(
        receipt_id=receipt_id,
        proposal_fingerprint=proposal_fingerprint,
        issued_at=issued_at,
        expires_at=expires_at,
        authority_signature=authority_signature,
    )


def verify_authorization_receipt(
    *,
    receipt: AuthorizationReceipt,
    signing_key: bytes,
    expected_proposal_fingerprint: str,
    now: datetime,
) -> ReceiptVerificationResult:
    expected_signature = _calculate_authority_signature(
        receipt_id=receipt.receipt_id,
        proposal_fingerprint=receipt.proposal_fingerprint,
        issued_at=receipt.issued_at,
        expires_at=receipt.expires_at,
        signing_key=signing_key,
    )

    if not hmac.compare_digest(
        receipt.authority_signature,
        expected_signature,
    ):
        return ReceiptVerificationResult(
            valid=False,
            reason="invalid_authority_signature",
        )

    if now >= receipt.expires_at:
        return ReceiptVerificationResult(
            valid=False,
            reason="receipt_expired",
        )

    if (
        receipt.proposal_fingerprint
        != expected_proposal_fingerprint
    ):
        return ReceiptVerificationResult(
            valid=False,
            reason="receipt_proposal_mismatch",
        )

    return ReceiptVerificationResult(
        valid=True,
        reason="receipt_valid",
    )