from dataclasses import dataclass
from datetime import datetime

from lockean_lite.authorization_receipt import (
    AuthorizationReceipt,
    verify_authorization_receipt,
)
from lockean_lite.proposal_fingerprint import (
    fingerprint_trade_proposal,
)
from lockean_lite.trade_proposal import TradeProposal


@dataclass(frozen=True)
class ExecutionAuthorityDecision:
    allowed: bool
    reason: str


def validate_execution_authority(
    *,
    proposal: TradeProposal,
    receipt: AuthorizationReceipt | None,
    signing_key: bytes,
    now: datetime,
) -> ExecutionAuthorityDecision:
    if receipt is None:
        return ExecutionAuthorityDecision(
            allowed=False,
            reason="authorization_receipt_required",
        )

    proposal_fingerprint = fingerprint_trade_proposal(
        proposal
    )

    verification = verify_authorization_receipt(
        receipt=receipt,
        signing_key=signing_key,
        expected_proposal_fingerprint=proposal_fingerprint,
        now=now,
    )

    if not verification.valid:
        return ExecutionAuthorityDecision(
            allowed=False,
            reason=verification.reason,
        )

    return ExecutionAuthorityDecision(
        allowed=True,
        reason="execution_authority_valid",
    )