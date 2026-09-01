from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

from lockean_lite.application_workflow import (
    run_trade_decision_cycle,
)
from lockean_lite.authorization_receipt import (
    issue_authorization_receipt,
)
from lockean_lite.autonomous_cycle import (
    run_autonomous_trade_cycle,
)
from lockean_lite.execution_gateway import (
    ExecutionProof,
    ExecutionSubmissionResult,
    PaperExecutionGateway,
    PaperExecutionGatewayResult,
)
from lockean_lite.option_leg import OptionLeg
from lockean_lite.proposal_fingerprint import (
    fingerprint_trade_proposal,
)
from lockean_lite.trade_proposal import (
    TradeProposal,
)


SIGNING_KEY = b"test-only-proof-key"

NOW = datetime(
    2026,
    9,
    1,
    6,
    0,
    tzinfo=timezone.utc,
)


def _proposal():
    return TradeProposal(
        proposal_id="proposal-proof-001",
        symbol="SPY",
        strategy="defined_risk_option",
        contracts=1,
        legs=(
            OptionLeg(
                option_type="call",
                strike=Decimal("775"),
                expiration=date(2026, 9, 18),
                side="buy",
            ),
            OptionLeg(
                option_type="call",
                strike=Decimal("780"),
                expiration=date(2026, 9, 18),
                side="sell",
            ),
        ),
        net_debit=Decimal("1.25"),
    )


def _receipt(proposal):
    return issue_authorization_receipt(
        receipt_id="receipt-proof-001",
        proposal_fingerprint=(
            fingerprint_trade_proposal(
                proposal
            )
        ),
        issued_at=NOW,
        expires_at=(
            NOW
            + timedelta(seconds=30)
        ),
        signing_key=SIGNING_KEY,
    )


def _proof(proposal):
    return ExecutionProof(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=(
            fingerprint_trade_proposal(
                proposal
            )
        ),
        authorization_receipt_id=(
            "receipt-proof-001"
        ),
        authorization_verification=(
            "execution_authority_valid"
        ),
        broker_order_id=(
            "paper-order-proof-001"
        ),
    )


def test_paper_gateway_returns_sanitized_execution_proof(
    monkeypatch,
):
    proposal = _proposal()
    receipt = _receipt(
        proposal
    )

    monkeypatch.setattr(
        "lockean_lite.execution_gateway.execute_authorized_paper_order",
        lambda **kwargs: ExecutionSubmissionResult(
            submitted=True,
            reason="paper_order_submitted",
            broker_order=SimpleNamespace(
                id="paper-order-proof-001",
            ),
        ),
    )

    gateway = PaperExecutionGateway(
        client=object(),
        signing_key=SIGNING_KEY,
        now_provider=lambda: (
            NOW
            + timedelta(seconds=5)
        ),
    )

    result = gateway.execute(
        proposal,
        receipt,
    )

    assert result.submitted is True
    assert result.reason == (
        "paper_order_submitted"
    )

    assert result.execution_proof == (
        _proof(proposal)
    )


def test_execution_proof_contains_no_execution_capability():
    fields = set(
        ExecutionProof.__dataclass_fields__
    )

    assert "authority_signature" not in fields
    assert "signing_key" not in fields
    assert "authorization_receipt" not in fields
    assert "broker_order" not in fields

    assert fields == {
        "proposal_id",
        "proposal_fingerprint",
        "authorization_receipt_id",
        "authorization_verification",
        "broker_order_id",
    }


def test_application_workflow_propagates_execution_proof():
    proposal = _proposal()
    receipt = _receipt(
        proposal
    )
    proof = _proof(
        proposal
    )

    class Authority:
        def evaluate(
            self,
            proposal,
            *,
            account_snapshot,
            validated_evidence,
        ):
            return SimpleNamespace(
                status="AUTHORIZED",
                reason="authorization_granted",
                authorization_receipt=receipt,
            )

    class Gateway:
        def execute(
            self,
            proposal,
            receipt,
        ):
            return PaperExecutionGatewayResult(
                submitted=True,
                reason="paper_order_submitted",
                execution_proof=proof,
            )

    result = run_trade_decision_cycle(
        proposal=proposal,
        account_snapshot=object(),
        evidence_validation_result=(
            SimpleNamespace(
                accepted=True,
                reason="evidence_valid",
                validated_evidence=object(),
            )
        ),
        authority=Authority(),
        execution_gateway=Gateway(),
    )

    assert result.status == "SUBMITTED"
    assert result.reason == (
        "paper_order_submitted"
    )

    assert result.execution_proof is proof


def test_autonomous_cycle_propagates_execution_proof(
    monkeypatch,
):
    proposal = _proposal()
    proof = _proof(
        proposal
    )

    monkeypatch.setattr(
        "lockean_lite.autonomous_cycle.evaluate_market_entry_policy",
        lambda **kwargs: SimpleNamespace(
            passed=True,
            reason="entry_policy_passed",
        ),
    )

    monkeypatch.setattr(
        "lockean_lite.autonomous_cycle.build_trade_proposal_from_recommendation",
        lambda **kwargs: proposal,
    )

    monkeypatch.setattr(
        "lockean_lite.autonomous_cycle.validate_market_evidence_for_proposal",
        lambda **kwargs: SimpleNamespace(
            accepted=True,
            reason="evidence_valid",
            validated_evidence=object(),
        ),
    )

    monkeypatch.setattr(
        "lockean_lite.autonomous_cycle.run_trade_decision_cycle",
        lambda **kwargs: SimpleNamespace(
            status="SUBMITTED",
            reason="paper_order_submitted",
            execution_proof=proof,
        ),
    )

    result = run_autonomous_trade_cycle(
        spy_evidence=object(),
        vix_evidence=object(),
        candidate_quotes_provider=(
            lambda: ("candidate",)
        ),
        recommendation_provider=(
            lambda candidates: "recommendation"
        ),
        account_snapshot_provider=(
            lambda: object()
        ),
        authority=object(),
        execution_gateway=object(),
    )

    assert result.status == "SUBMITTED"
    assert result.reason == (
        "paper_order_submitted"
    )

    assert result.execution_proof is proof