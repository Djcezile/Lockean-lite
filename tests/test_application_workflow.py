from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from lockean_lite.application_workflow import (
    run_trade_decision_cycle,
)
from lockean_lite.authorization_receipt import (
    AuthorizationReceipt,
)
from lockean_lite.evidence_validation import (
    EvidenceValidationResult,
    ValidatedMarketEvidence,
)
from lockean_lite.lockean_authority import (
    AuthorityDecision,
)
from lockean_lite.option_leg import OptionLeg
from lockean_lite.paper_account_snapshot import (
    PaperAccountSnapshot,
)
from lockean_lite.trade_proposal import TradeProposal


AS_OF = datetime(
    2026,
    8,
    28,
    20,
    0,
    tzinfo=timezone.utc,
)


def _proposal():
    return TradeProposal(
        proposal_id="proposal-cycle-001",
        symbol="SPY",
        strategy="defined_risk_option",
        contracts=1,
        legs=(
            OptionLeg(
                option_type="call",
                strike=Decimal("500"),
                expiration=date(2026, 9, 18),
                side="buy",
            ),
            OptionLeg(
                option_type="call",
                strike=Decimal("505"),
                expiration=date(2026, 9, 18),
                side="sell",
            ),
        ),
        net_debit=Decimal("1.00"),
    )


def _account():
    return PaperAccountSnapshot(
        status="ACTIVE",
        currency="USD",
        trading_blocked=False,
        options_buying_power=Decimal("1000"),
        options_approved_level=3,
        options_trading_level=3,
    )


class FakeAuthority:
    def __init__(self, decision):
        self.decision = decision
        self.calls = []

    def evaluate(
        self,
        proposal,
        account_snapshot=None,
        validated_evidence=None,
    ):
        self.calls.append(
            (
                proposal,
                account_snapshot,
                validated_evidence,
            )
        )

        return self.decision


class FakeExecutionGateway:
    def __init__(self):
        self.calls = []

    def execute(
        self,
        proposal,
        receipt,
    ):
        self.calls.append(
            (proposal, receipt)
        )

        return "submitted"


def test_cycle_stops_before_authority_and_execution_when_evidence_fails():
    authority = FakeAuthority(
        decision=None,
    )

    gateway = FakeExecutionGateway()

    result = run_trade_decision_cycle(
        proposal=_proposal(),
        account_snapshot=_account(),
        evidence_validation_result=(
            EvidenceValidationResult(
                accepted=False,
                reason="breakout_filter_failed",
            )
        ),
        authority=authority,
        execution_gateway=gateway,
    )

    assert result.status == "REJECTED"
    assert result.reason == "breakout_filter_failed"

    assert authority.calls == []
    assert gateway.calls == []


def test_cycle_stops_before_execution_when_authority_rejects():
    authority = FakeAuthority(
        decision=AuthorityDecision(
            status="REJECTED",
            reason="max_loss_exceeds_limit",
            proposal_id="proposal-cycle-001",
        )
    )

    gateway = FakeExecutionGateway()

    validated = ValidatedMarketEvidence(
        proposal_fingerprint="fingerprint",
        spy_evidence_id="spy",
        vix_evidence_id="vix",
        as_of=AS_OF,
        spy_source="alpaca",
        vix_source="cboe",
    )

    result = run_trade_decision_cycle(
        proposal=_proposal(),
        account_snapshot=_account(),
        evidence_validation_result=(
            EvidenceValidationResult(
                accepted=True,
                reason="evidence_validated",
                validated_evidence=validated,
            )
        ),
        authority=authority,
        execution_gateway=gateway,
    )

    assert result.status == "REJECTED"
    assert result.reason == "max_loss_exceeds_limit"

    assert len(authority.calls) == 1
    assert gateway.calls == []


def test_cycle_reaches_execution_only_after_authority_receipt_exists():
    receipt = AuthorizationReceipt(
        receipt_id="receipt-cycle-001",
        proposal_fingerprint="fingerprint",
        issued_at=AS_OF,
        expires_at=AS_OF,
        authority_signature="signature",
    )

    authority = FakeAuthority(
        decision=AuthorityDecision(
            status="AUTHORIZED",
            reason="authorization_granted",
            proposal_id="proposal-cycle-001",
            authorization_receipt=receipt,
        )
    )

    gateway = FakeExecutionGateway()

    validated = ValidatedMarketEvidence(
        proposal_fingerprint="fingerprint",
        spy_evidence_id="spy",
        vix_evidence_id="vix",
        as_of=AS_OF,
        spy_source="alpaca",
        vix_source="cboe",
    )

    result = run_trade_decision_cycle(
        proposal=_proposal(),
        account_snapshot=_account(),
        evidence_validation_result=(
            EvidenceValidationResult(
                accepted=True,
                reason="evidence_validated",
                validated_evidence=validated,
            )
        ),
        authority=authority,
        execution_gateway=gateway,
    )

    assert result.status == "SUBMITTED"
    assert result.reason == "paper_order_submitted"

    assert len(authority.calls) == 1
    assert len(gateway.calls) == 1

def test_cycle_preserves_exact_execution_gateway_failure_reason():
    receipt = AuthorizationReceipt(
        receipt_id="receipt-cycle-002",
        proposal_fingerprint="fingerprint",
        issued_at=AS_OF,
        expires_at=AS_OF,
        authority_signature="signature",
    )

    authority = FakeAuthority(
        decision=AuthorityDecision(
            status="AUTHORIZED",
            reason="authorization_granted",
            proposal_id="proposal-cycle-001",
            authorization_receipt=receipt,
        )
    )

    class RejectingGateway:
        def execute(
            self,
            proposal,
            receipt,
        ):
            return "receipt_expired"

    validated = ValidatedMarketEvidence(
        proposal_fingerprint="fingerprint",
        spy_evidence_id="spy",
        vix_evidence_id="vix",
        as_of=AS_OF,
        spy_source="alpaca",
        vix_source="cboe",
    )

    result = run_trade_decision_cycle(
        proposal=_proposal(),
        account_snapshot=_account(),
        evidence_validation_result=(
            EvidenceValidationResult(
                accepted=True,
                reason="evidence_validated",
                validated_evidence=validated,
            )
        ),
        authority=authority,
        execution_gateway=RejectingGateway(),
    )

    assert result.status == "REJECTED"
    assert result.reason == "receipt_expired"