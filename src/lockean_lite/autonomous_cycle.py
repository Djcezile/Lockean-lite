from dataclasses import dataclass
from lockean_lite.execution_gateway import (
    ExecutionProof,
)

from lockean_lite.application_workflow import (
    run_trade_decision_cycle,
)
from lockean_lite.evidence_validation import (
    validate_market_evidence_for_proposal,
)
from lockean_lite.market_entry_policy import (
    evaluate_market_entry_policy,
)
from lockean_lite.trade_recommendation import (
    build_trade_proposal_from_recommendation,
)


@dataclass(frozen=True)
class AutonomousTradeCycleResult:
    status: str
    reason: str
    execution_proof: ExecutionProof | None = None


def run_autonomous_trade_cycle(
    *,
    spy_evidence,
    vix_evidence,
    candidate_quotes_provider,
    recommendation_provider,
    account_snapshot_provider,
    authority,
    execution_gateway,
) -> AutonomousTradeCycleResult:
    market_evaluation = evaluate_market_entry_policy(
        spy_evidence=spy_evidence,
        vix_evidence=vix_evidence,
    )

    if not market_evaluation.passed:
        return AutonomousTradeCycleResult(
            status="REJECTED",
            reason=market_evaluation.reason,
        )

    candidate_quotes = (
        candidate_quotes_provider()
    )

    recommendation = recommendation_provider(
        candidate_quotes
    )

    try:
        proposal = (
            build_trade_proposal_from_recommendation(
                recommendation=recommendation,
                candidate_quotes=candidate_quotes,
            )
        )
    except ValueError as error:
        return AutonomousTradeCycleResult(
            status="REJECTED",
            reason=str(error),
        )

    evidence_validation_result = (
        validate_market_evidence_for_proposal(
            proposal=proposal,
            spy_evidence=spy_evidence,
            vix_evidence=vix_evidence,
        )
    )

    if not evidence_validation_result.accepted:
        return AutonomousTradeCycleResult(
            status="REJECTED",
            reason=evidence_validation_result.reason,
        )

    account_snapshot = (
        account_snapshot_provider()
    )

    cycle_result = run_trade_decision_cycle(
        proposal=proposal,
        account_snapshot=account_snapshot,
        evidence_validation_result=(
            evidence_validation_result
        ),
        authority=authority,
        execution_gateway=execution_gateway,
    )

    return AutonomousTradeCycleResult(
        status=cycle_result.status,
        reason=cycle_result.reason,
        execution_proof=(
            cycle_result.execution_proof
        ),
    )