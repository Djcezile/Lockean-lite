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

from lockean_lite.alpaca_execution_adapter import (
    build_authorized_mleg_limit_order,
    resolve_option_contract_symbols,
)

from datetime import datetime, timezone
from typing import Callable

@dataclass(frozen=True)
class ExecutionAuthorityDecision:
    allowed: bool
    reason: str

@dataclass(frozen=True)
class ExecutionSubmissionResult:
    submitted: bool
    reason: str
    broker_order: object | None = None


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


def execute_authorized_paper_order(
    *,
    client,
    proposal: TradeProposal,
    receipt: AuthorizationReceipt | None,
    signing_key: bytes,
    now: datetime,
) -> ExecutionSubmissionResult:
    authority_decision = validate_execution_authority(
        proposal=proposal,
        receipt=receipt,
        signing_key=signing_key,
        now=now,
    )

    if not authority_decision.allowed:
        return ExecutionSubmissionResult(
            submitted=False,
            reason=authority_decision.reason,
        )

    contract_symbols = resolve_option_contract_symbols(
        client=client,
        proposal=proposal,
    )

    order_request = build_authorized_mleg_limit_order(
        proposal=proposal,
        contract_symbols=contract_symbols,
    )

    broker_order = client.submit_order(
        order_data=order_request,
    )

    return ExecutionSubmissionResult(
        submitted=True,
        reason="paper_order_submitted",
        broker_order=broker_order,
    )

class PaperExecutionGateway:
    def __init__(
        self,
        *,
        client,
        signing_key: bytes,
        now_provider: Callable[[], datetime] | None = None,
    ):
        self.client = client
        self.signing_key = signing_key
        self.now_provider = (
            now_provider
            if now_provider is not None
            else lambda: datetime.now(timezone.utc)
        )

    def execute(
        self,
        proposal: TradeProposal,
        receipt: AuthorizationReceipt,
    ) -> str:
        result = execute_authorized_paper_order(
            client=self.client,
            proposal=proposal,
            receipt=receipt,
            signing_key=self.signing_key,
            now=self.now_provider(),
        )

        if result.submitted:
            return "submitted"

        return result.reason