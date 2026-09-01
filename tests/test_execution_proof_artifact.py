from pathlib import Path

import pytest

from lockean_lite.autonomous_cycle import (
    AutonomousTradeCycleResult,
)
from lockean_lite.execution_gateway import (
    ExecutionProof,
)
from lockean_lite.execution_proof_artifact import (
    render_execution_proof_artifact,
    write_execution_proof_artifact,
)


def _submitted_result():
    return AutonomousTradeCycleResult(
        status="SUBMITTED",
        reason="paper_order_submitted",
        execution_proof=ExecutionProof(
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
        ),
    )


def test_artifact_renderer_passes_exact_lockean_result_to_existing_view(
    monkeypatch,
):
    result = _submitted_result()

    captured = {}

    def fake_renderer(value):
        captured["result"] = value

        return (
            "<html>"
            "LOCKEAN EXECUTION PROOF"
            "</html>"
        )

    monkeypatch.setattr(
        "lockean_lite.execution_proof_artifact.render_execution_result_html",
        fake_renderer,
    )

    html = render_execution_proof_artifact(
        result
    )

    assert captured["result"] is result

    assert html == (
        "<html>"
        "LOCKEAN EXECUTION PROOF"
        "</html>"
    )


def test_artifact_writer_writes_exact_rendered_html(
    monkeypatch,
    tmp_path,
):
    result = _submitted_result()

    expected_html = (
        "<html>"
        "LOCKEAN EXECUTION PROOF"
        "</html>"
    )

    monkeypatch.setattr(
        "lockean_lite.execution_proof_artifact.render_execution_proof_artifact",
        lambda value: expected_html,
    )

    output_path = (
        tmp_path
        / "execution-proof.html"
    )

    written_path = write_execution_proof_artifact(
        result=result,
        output_path=output_path,
    )

    assert written_path == output_path

    assert output_path.read_text(
        encoding="utf-8"
    ) == expected_html


def test_artifact_write_failure_preserves_original_transaction_truth(
    monkeypatch,
    tmp_path,
):
    result = _submitted_result()

    original_status = (
        result.status
    )

    original_reason = (
        result.reason
    )

    monkeypatch.setattr(
        "lockean_lite.execution_proof_artifact.render_execution_proof_artifact",
        lambda value: "<html></html>",
    )

    output_path = (
        tmp_path
        / "missing-directory"
        / "execution-proof.html"
    )

    with pytest.raises(
        ValueError,
        match=(
            "execution_proof_output_write_failed"
        ),
    ):
        write_execution_proof_artifact(
            result=result,
            output_path=output_path,
        )

    assert result.status == (
        original_status
    )

    assert result.reason == (
        original_reason
    )

    assert result.status == "SUBMITTED"
    assert result.reason == (
        "paper_order_submitted"
    )


def test_artifact_writer_can_render_rejected_result_without_inventing_proof(
    tmp_path,
):
    result = AutonomousTradeCycleResult(
        status="REJECTED",
        reason="max_loss_exceeds_limit",
        execution_proof=None,
    )

    output_path = (
        tmp_path
        / "rejected-result.html"
    )

    write_execution_proof_artifact(
        result=result,
        output_path=output_path,
    )

    html = output_path.read_text(
        encoding="utf-8"
    )

    assert "REJECTED" in html
    assert "max_loss_exceeds_limit" in html

    assert (
        "NO EXECUTION PROOF"
        in html
    )


def test_artifact_module_has_no_execution_or_decision_authority():
    import lockean_lite.execution_proof_artifact as artifact

    forbidden_names = (
        "run_production_autonomous_cycle",
        "run_autonomous_trade_cycle",
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
            artifact,
            name,
        )