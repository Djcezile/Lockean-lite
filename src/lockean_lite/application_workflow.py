from dataclasses import dataclass

from lockean_lite.evidence_validation import (
    EvidenceValidationResult,
)
from lockean_lite.paper_account_snapshot import (
    PaperAccountSnapshot,
)
from lockean_lite.trade_proposal import TradeProposal


@dataclass(frozen=True)
class TradeDecisionCycleResult:
    status: str
    reason: str


def run_trade_decision_cycle(
    *,
    proposal: TradeProposal,
    account_snapshot: PaperAccountSnapshot,
    evidence_validation_result: EvidenceValidationResult,
    authority,
    execution_gateway,
) -> TradeDecisionCycleResult:
    if not evidence_validation_result.accepted:
        return TradeDecisionCycleResult(
            status="REJECTED",
            reason=evidence_validation_result.reason,
        )

    validated_evidence = (
        evidence_validation_result.validated_evidence
    )

    if validated_evidence is None:
        return TradeDecisionCycleResult(
            status="REJECTED",
            reason="validated_evidence_required",
        )

    authority_decision = authority.evaluate(
        proposal,
        account_snapshot=account_snapshot,
        validated_evidence=validated_evidence,
    )

    if authority_decision.status != "AUTHORIZED":
        return TradeDecisionCycleResult(
            status="REJECTED",
            reason=authority_decision.reason,
        )

    receipt = (
        authority_decision.authorization_receipt
    )

    if receipt is None:
        return TradeDecisionCycleResult(
            status="REJECTED",
            reason="authorization_receipt_required",
        )

    execution_result = execution_gateway.execute(
        proposal,
        receipt,
    )

    if execution_result != "submitted":
        return TradeDecisionCycleResult(
            status="REJECTED",
            reason="execution_failed",
        )

    return TradeDecisionCycleResult(
        status="SUBMITTED",
        reason="paper_order_submitted",
    )