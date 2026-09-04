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
from lockean_lite.agent_market_context import (
    build_agent_market_context,
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
    market_context = build_agent_market_context(
        spy_evidence=spy_evidence,
        vix_evidence=vix_evidence,
    )

    candidate_quotes = (
        candidate_quotes_provider()
    )

    recommendation = recommendation_provider(
        candidate_quotes,
        market_context=market_context,
    )

    if recommendation is None:
        return AutonomousTradeCycleResult(
            status="NO_TRADE",
            reason="agent_declined_trade",
        )

    # Session portfolio capacity is counted in spread units. One autonomous
    # decision may consume exactly one unit so a single recommendation cannot
    # leap past the five-spread portfolio cap before the next Alpaca refresh.
    if recommendation.contracts != 1:
        return AutonomousTradeCycleResult(
            status="REJECTED",
            reason="autonomous_contract_quantity_must_be_one",
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
