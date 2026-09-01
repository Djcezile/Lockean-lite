from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from lockean_lite.authorization_receipt import (
    issue_authorization_receipt,
)
from lockean_lite.execution_gateway import (
    validate_execution_authority,
)
from lockean_lite.option_leg import OptionLeg
from lockean_lite.proposal_fingerprint import (
    fingerprint_trade_proposal,
)
from lockean_lite.trade_proposal import TradeProposal

from types import SimpleNamespace

import pytest

from alpaca.trading.enums import ContractType

from lockean_lite.execution_gateway import (
    execute_authorized_paper_order,
    validate_execution_authority,
)

from lockean_lite.execution_gateway import (
    ExecutionSubmissionResult,
    PaperExecutionGateway,
    execute_authorized_paper_order,
    validate_execution_authority,
)

class FakeExecutionClient:
    def __init__(self):
        self.contract_requests = []
        self.submitted_orders = []

    def get_option_contracts(self, request):
        self.contract_requests.append(request)

        strike = Decimal(
            str(request.strike_price_gte)
        )

        symbol = (
            "SPY260918C00500000"
            if strike == Decimal("500")
            else "SPY260918C00505000"
        )

        contract = SimpleNamespace(
            symbol=symbol,
            underlying_symbol="SPY",
            expiration_date=date(2026, 9, 18),
            type=ContractType.CALL,
            strike_price=float(strike),
            tradable=True,
        )

        return SimpleNamespace(
            option_contracts=[contract],
        )

    def submit_order(self, *, order_data):
        self.submitted_orders.append(order_data)

        return SimpleNamespace(
            id="paper-order-001",
        )

TEST_SIGNING_KEY = b"test-only-execution-gateway-key"

NOW = datetime(
    2026,
    8,
    31,
    0,
    45,
    tzinfo=timezone.utc,
)

@pytest.mark.parametrize(
    "scenario",
    [
        "missing",
        "forged",
        "expired",
        "tampered",
    ],
)

def test_execution_gateway_never_calls_broker_for_invalid_authority(
    scenario,
):
    original_proposal = _proposal(contracts=1)
    proposal = original_proposal
    receipt = _receipt_for(original_proposal)
    now = NOW + timedelta(seconds=5)

    if scenario == "missing":
        receipt = None

    elif scenario == "forged":
        receipt = replace(
            receipt,
            authority_signature="forged",
        )

    elif scenario == "expired":
        now = NOW + timedelta(seconds=30)

    elif scenario == "tampered":
        proposal = _proposal(contracts=2)

    client = FakeExecutionClient()

    result = execute_authorized_paper_order(
        client=client,
        proposal=proposal,
        receipt=receipt,
        signing_key=TEST_SIGNING_KEY,
        now=now,
    )

    assert result.submitted is False

    assert client.contract_requests == []
    assert client.submitted_orders == []

def test_execution_gateway_submits_exactly_once_for_valid_authority():
    proposal = _proposal(contracts=1)
    receipt = _receipt_for(proposal)

    client = FakeExecutionClient()

    result = execute_authorized_paper_order(
        client=client,
        proposal=proposal,
        receipt=receipt,
        signing_key=TEST_SIGNING_KEY,
        now=NOW + timedelta(seconds=5),
    )

    assert result.submitted is True
    assert result.reason == "paper_order_submitted"

    assert len(client.contract_requests) == 2
    assert len(client.submitted_orders) == 1

    submitted_order = client.submitted_orders[0]

    assert submitted_order.qty == 1
    assert submitted_order.limit_price == 1.0

    assert result.broker_order.id == "paper-order-001"


def _proposal(contracts=1):
    buy_leg = OptionLeg(
        option_type="call",
        strike=Decimal("500"),
        expiration=date(2026, 9, 18),
        side="buy",
    )

    sell_leg = OptionLeg(
        option_type="call",
        strike=Decimal("505"),
        expiration=date(2026, 9, 18),
        side="sell",
    )

    return TradeProposal(
        proposal_id="proposal-029",
        symbol="SPY",
        strategy="defined_risk_option",
        contracts=contracts,
        legs=(buy_leg, sell_leg),
        net_debit=Decimal("1.00"),
    )


def _receipt_for(proposal):
    return issue_authorization_receipt(
        receipt_id="receipt-gateway-001",
        proposal_fingerprint=fingerprint_trade_proposal(
            proposal
        ),
        issued_at=NOW,
        expires_at=NOW + timedelta(seconds=30),
        signing_key=TEST_SIGNING_KEY,
    )


def test_execution_gateway_rejects_missing_receipt():
    decision = validate_execution_authority(
        proposal=_proposal(),
        receipt=None,
        signing_key=TEST_SIGNING_KEY,
        now=NOW,
    )

    assert decision.allowed is False
    assert decision.reason == "authorization_receipt_required"


def test_execution_gateway_rejects_forged_receipt():
    proposal = _proposal()
    receipt = _receipt_for(proposal)

    forged = replace(
        receipt,
        authority_signature="not-a-valid-signature",
    )

    decision = validate_execution_authority(
        proposal=proposal,
        receipt=forged,
        signing_key=TEST_SIGNING_KEY,
        now=NOW + timedelta(seconds=5),
    )

    assert decision.allowed is False
    assert decision.reason == "invalid_authority_signature"


def test_execution_gateway_rejects_expired_receipt():
    proposal = _proposal()

    decision = validate_execution_authority(
        proposal=proposal,
        receipt=_receipt_for(proposal),
        signing_key=TEST_SIGNING_KEY,
        now=NOW + timedelta(seconds=30),
    )

    assert decision.allowed is False
    assert decision.reason == "receipt_expired"


def test_execution_gateway_rejects_tampered_proposal():
    original = _proposal(contracts=1)
    receipt = _receipt_for(original)

    tampered = _proposal(contracts=2)

    decision = validate_execution_authority(
        proposal=tampered,
        receipt=receipt,
        signing_key=TEST_SIGNING_KEY,
        now=NOW + timedelta(seconds=5),
    )

    assert decision.allowed is False
    assert decision.reason == "receipt_proposal_mismatch"


def test_execution_gateway_allows_exact_authorized_proposal():
    proposal = _proposal()

    decision = validate_execution_authority(
        proposal=proposal,
        receipt=_receipt_for(proposal),
        signing_key=TEST_SIGNING_KEY,
        now=NOW + timedelta(seconds=5),
    )

    assert decision.allowed is True
    assert decision.reason == "execution_authority_valid"

def test_paper_execution_gateway_uses_receipt_gated_submission(
    monkeypatch,
):
    proposal = _proposal()
    receipt = _receipt_for(proposal)

    client = object()

    expected_now = NOW + timedelta(seconds=5)

    calls = []

    def fake_execute_authorized_paper_order(
        *,
        client,
        proposal,
        receipt,
        signing_key,
        now,
    ):
        calls.append(
            (
                client,
                proposal,
                receipt,
                signing_key,
                now,
            )
        )

        return ExecutionSubmissionResult(
            submitted=True,
            reason="paper_order_submitted",
            broker_order=SimpleNamespace(
                id="paper-order-001",
            ),
        )

    monkeypatch.setattr(
        "lockean_lite.execution_gateway.execute_authorized_paper_order",
        fake_execute_authorized_paper_order,
    )

    gateway = PaperExecutionGateway(
        client=client,
        signing_key=TEST_SIGNING_KEY,
        now_provider=lambda: expected_now,
    )

    result = gateway.execute(
        proposal,
        receipt,
    )

    assert result.submitted is True
    assert result.reason == (
        "paper_order_submitted"
    )
    assert result.execution_proof is not None
    assert (
        result.execution_proof.broker_order_id
        == "paper-order-001"
    )
    assert (
        result.execution_proof.authorization_receipt_id
        == receipt.receipt_id
    )

    assert calls == [
        (
            client,
            proposal,
            receipt,
            TEST_SIGNING_KEY,
            expected_now,
        )
    ]


def test_paper_execution_gateway_preserves_exact_rejection_reason(
    monkeypatch,
):
    proposal = _proposal()
    receipt = _receipt_for(proposal)

    monkeypatch.setattr(
        "lockean_lite.execution_gateway.execute_authorized_paper_order",
        lambda **kwargs: ExecutionSubmissionResult(
            submitted=False,
            reason="receipt_expired",
        ),
    )

    gateway = PaperExecutionGateway(
        client=object(),
        signing_key=TEST_SIGNING_KEY,
        now_provider=lambda: NOW,
    )

    result = gateway.execute(
        proposal,
        receipt,
    )

    assert result.submitted is False
    assert result.reason == "receipt_expired"
    assert result.execution_proof is None