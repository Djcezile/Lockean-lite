from dataclasses import dataclass
from datetime import datetime

from lockean_lite.market_entry_policy import (
    evaluate_market_entry_policy,
)
from lockean_lite.market_evidence import MarketEvidence
from lockean_lite.proposal_fingerprint import (
    fingerprint_trade_proposal,
)
from lockean_lite.trade_proposal import TradeProposal


SUPPORTED_SPY_EVIDENCE_SOURCE = "alpaca"
SUPPORTED_VIX_EVIDENCE_SOURCE = "cboe"
SUPPORTED_VOLATILITY_SYMBOL = "VIX"


@dataclass(frozen=True)
class ValidatedMarketEvidence:
    proposal_fingerprint: str
    spy_evidence_id: str
    vix_evidence_id: str
    as_of: datetime
    spy_source: str
    vix_source: str


@dataclass(frozen=True)
class EvidenceValidationResult:
    accepted: bool
    reason: str
    validated_evidence: ValidatedMarketEvidence | None = None


def validate_market_evidence_for_proposal(
    proposal: TradeProposal,
    spy_evidence: MarketEvidence,
    vix_evidence: MarketEvidence,
) -> EvidenceValidationResult:
    if spy_evidence.symbol != proposal.symbol:
        return EvidenceValidationResult(
            accepted=False,
            reason="proposal_evidence_symbol_mismatch",
        )

    if vix_evidence.symbol != SUPPORTED_VOLATILITY_SYMBOL:
        return EvidenceValidationResult(
            accepted=False,
            reason="volatility_evidence_symbol_mismatch",
        )

    if (
        spy_evidence.source
        != SUPPORTED_SPY_EVIDENCE_SOURCE
        or vix_evidence.source
        != SUPPORTED_VIX_EVIDENCE_SOURCE
    ):
        return EvidenceValidationResult(
            accepted=False,
            reason="unsupported_evidence_source",
        )

    if spy_evidence.as_of != vix_evidence.as_of:
        return EvidenceValidationResult(
            accepted=False,
            reason="evidence_as_of_mismatch",
        )

    if (
        not spy_evidence.bars
        or not vix_evidence.bars
        or spy_evidence.bars[-1].timestamp != spy_evidence.as_of
        or vix_evidence.bars[-1].timestamp != vix_evidence.as_of
    ):
        return EvidenceValidationResult(
            accepted=False,
            reason="evidence_as_of_inconsistent",
        )

    entry_evaluation = evaluate_market_entry_policy(
        spy_evidence=spy_evidence,
        vix_evidence=vix_evidence,
    )

    if not entry_evaluation.passed:
        return EvidenceValidationResult(
            accepted=False,
            reason=entry_evaluation.reason,
        )

    validated_evidence = ValidatedMarketEvidence(
        proposal_fingerprint=fingerprint_trade_proposal(proposal),
        spy_evidence_id=spy_evidence.evidence_id,
        vix_evidence_id=vix_evidence.evidence_id,
        as_of=spy_evidence.as_of,
        spy_source=SUPPORTED_SPY_EVIDENCE_SOURCE,
        vix_source=SUPPORTED_VIX_EVIDENCE_SOURCE,
    )

    return EvidenceValidationResult(
        accepted=True,
        reason="evidence_validated",
        validated_evidence=validated_evidence,
    )