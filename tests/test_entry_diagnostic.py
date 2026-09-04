from types import SimpleNamespace

import pytest

from lockean_lite.entry_diagnostic import (
    DiagnosticExecutionGateway,
    main,
)


def test_diagnostic_gateway_can_never_submit_broker_order():
    gateway = DiagnosticExecutionGateway()

    result = gateway.execute(
        proposal=object(),
        receipt=object(),
    )

    assert result.submitted is False
    assert result.reason == "diagnostic_execution_disabled"
    assert result.execution_proof is None


def test_entry_diagnostic_reports_machine_safe_value_error(
    monkeypatch,
    capsys,
):
    monkeypatch.setenv(
        "LOCKEAN_AUTHORIZATION_SIGNING_KEY",
        "diagnostic-key",
    )

    def fail_cycle(**kwargs):
        raise ValueError("ai_model_request_failed")

    monkeypatch.setattr(
        "lockean_lite.entry_diagnostic.run_live_entry_diagnostic",
        fail_cycle,
    )

    exit_code = main(
        [
            "--completed-through",
            "2026-09-04",
            "--expiration",
            "2026-09-18",
        ]
    )

    captured = capsys.readouterr().out

    assert exit_code == 1
    assert "ValueError | ai_model_request_failed" in captured


def test_entry_diagnostic_redacts_free_form_error_text(
    monkeypatch,
    capsys,
):
    monkeypatch.setenv(
        "LOCKEAN_AUTHORIZATION_SIGNING_KEY",
        "diagnostic-key",
    )

    def fail_cycle(**kwargs):
        raise ValueError("provider token=do-not-log")

    monkeypatch.setattr(
        "lockean_lite.entry_diagnostic.run_live_entry_diagnostic",
        fail_cycle,
    )

    exit_code = main(
        [
            "--completed-through",
            "2026-09-04",
            "--expiration",
            "2026-09-18",
        ]
    )

    captured = capsys.readouterr().out

    assert exit_code == 1
    assert "ValueError | value_error" in captured
    assert "do-not-log" not in captured


def test_entry_diagnostic_renders_non_executing_result(
    monkeypatch,
    capsys,
):
    monkeypatch.setenv(
        "LOCKEAN_AUTHORIZATION_SIGNING_KEY",
        "diagnostic-key",
    )

    monkeypatch.setattr(
        "lockean_lite.entry_diagnostic.run_live_entry_diagnostic",
        lambda **kwargs: SimpleNamespace(
            status="REJECTED",
            reason="diagnostic_execution_disabled",
        ),
    )

    exit_code = main(
        [
            "--completed-through",
            "2026-09-04",
            "--expiration",
            "2026-09-18",
            "--activity-mode",
            "active_paper",
        ]
    )

    captured = capsys.readouterr().out

    assert exit_code == 0
    assert (
        "DIAGNOSTIC RESULT: REJECTED | "
        "diagnostic_execution_disabled"
    ) in captured
    assert "BROKER EXECUTION: DISABLED" in captured
