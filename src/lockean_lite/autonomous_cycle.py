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
    diagnostics: tuple[str, ...] = ()


def _agent_diagnostics(
    *,
    recommendation_provider,
    market_context: dict[str, str],
    recommendation,
) -> tuple[str, ...]:
    context_text = ";".join(
        f"{key}={value}"
        for key, value in market_context.items()
    )

    decision = getattr(
        recommendation_provider,
        "last_decision",
        None,
    )

    if decision is None:
        decision = (
            "NO_TRADE"
            if recommendation is None
            else "TRADE"
        )

    rationale = getattr(
        recommendation_provider,
        "last_decision_rationale",
        None,
    ) or "not_provided"

    return (
        f"agent_context={context_text}",
        f"agent_decision={decision}",
        f"agent_rationale={rationale}",
    )


def run_autonomous_trade_cycle(
    *,
    spy_evidence,
    vix_evidence,
    candidate_quotes_provider,
    recommendation_provider,
    account_snapshot_provider,
    authority,
    execution_gateway,
    proposal_policy_checker=None,
    intraday_context: dict[str, str] | None = None,
) -> AutonomousTradeCycleResult:
    market_context = build_agent_market_context(
        spy_evidence=spy_evidence,
        vix_evidence=vix_evidence,
        intraday_context=intraday_context,
    )

    candidate_quotes = (
        candidate_quotes_provider()
    )

    recommendation = recommendation_provider(
        candidate_quotes,
        market_context=market_context,
    )

    diagnostics = _agent_diagnostics(
        recommendation_provider=recommendation_provider,
        market_context=market_context,
        recommendation=recommendation,
    )

    if recommendation is None:
        return AutonomousTradeCycleResult(
            status="NO_TRADE",
            reason="agent_declined_trade",
            diagnostics=diagnostics,
        )

    # Session portfolio capacity is counted in spread units. One autonomous
    # decision may consume exactly one unit so a single recommendation cannot
    # leap past the five-spread portfolio cap before the next Alpaca refresh.
    if recommendation.contracts != 1:
        return AutonomousTradeCycleResult(
            status="REJECTED",
            reason="autonomous_contract_quantity_must_be_one",
            diagnostics=diagnostics,
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
            diagnostics=diagnostics,
        )

    if proposal_policy_checker is not None:
        policy_decision = proposal_policy_checker(
            proposal,
            candidate_quotes,
        )

        if not policy_decision.allowed:
            return AutonomousTradeCycleResult(
                status="REJECTED",
                reason=policy_decision.reason,
                diagnostics=diagnostics,
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
            diagnostics=diagnostics,
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
        diagnostics=diagnostics,
    )
