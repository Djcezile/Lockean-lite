from lockean_lite.autonomous_cycle import (
    AutonomousTradeCycleResult,
)
from lockean_lite.execution_gateway import (
    ExecutionProof,
)
from lockean_lite.visual_execution_proof import (
    render_execution_result_html,
)


def _execution_proof():
    return ExecutionProof(
        proposal_id="proposal-proof-001",
        proposal_fingerprint=(
            "abc123def456"
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


def _submitted_result():
    return AutonomousTradeCycleResult(
        status="SUBMITTED",
        reason="paper_order_submitted",
        execution_proof=_execution_proof(),
    )


def test_success_view_displays_exact_lockean_result():
    html = render_execution_result_html(
        _submitted_result()
    )

    assert "LOCKEAN" in html

    assert "SUBMITTED" in html
    assert "paper_order_submitted" in html

    assert "proposal-proof-001" in html
    assert "abc123def456" in html
    assert "receipt-proof-001" in html

    assert (
        "execution_authority_valid"
        in html
    )

    assert (
        "paper-order-proof-001"
        in html
    )


def test_success_view_does_not_invent_authorization_status():
    html = render_execution_result_html(
        _submitted_result()
    )

    assert "AUTHORIZED" not in html
    assert "APPROVED" not in html
    assert "SAFE TO TRADE" not in html


def test_success_view_displays_no_proof_when_lockean_supplies_none():
    result = AutonomousTradeCycleResult(
        status="REJECTED",
        reason="max_loss_exceeds_limit",
        execution_proof=None,
    )

    html = render_execution_result_html(
        result
    )

    assert "REJECTED" in html
    assert "max_loss_exceeds_limit" in html

    assert (
        "NO EXECUTION PROOF"
        in html
    )


def test_success_view_has_no_authority_or_execution_dependencies():
    import lockean_lite.visual_execution_proof as visual

    forbidden_names = (
        "LockeanAuthority",
        "PaperExecutionGateway",
        "AuthorizationReceipt",
        "verify_authorization_receipt",
        "issue_authorization_receipt",
        "execute_authorized_paper_order",
        "fingerprint_trade_proposal",
        "evaluate_market_entry_policy",
        "submit_order",
    )

    for name in forbidden_names:
        assert not hasattr(
            visual,
            name,
        )