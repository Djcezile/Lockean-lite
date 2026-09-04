from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from lockean_lite.entry_diagnostic import (
    DiagnosticExecutionGateway,
    main,
    run_live_entry_diagnostic,
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


def test_live_entry_diagnostic_uses_api_account_snapshot_provider(
    monkeypatch,
):
    captured = {}

    fake_credentials = SimpleNamespace(
        api_key="test-api-key",
        secret_key="test-secret-key",
    )
    fake_spy_evidence = SimpleNamespace(
        bars=(
            SimpleNamespace(
                close=Decimal("769.28"),
            ),
        )
    )
    fake_vix_evidence = object()
    fake_account_provider = lambda: "account"
    expected_result = object()

    monkeypatch.setattr(
        "lockean_lite.entry_diagnostic.load_alpaca_credentials_from_environment",
        lambda: fake_credentials,
    )
    monkeypatch.setattr(
        "lockean_lite.entry_diagnostic.StockHistoricalDataClient",
        lambda *args, **kwargs: object(),
    )
    monkeypatch.setattr(
        "lockean_lite.entry_diagnostic.OptionHistoricalDataClient",
        lambda *args, **kwargs: object(),
    )
    monkeypatch.setattr(
        "lockean_lite.entry_diagnostic.create_paper_trading_client_from_environment",
        lambda: object(),
    )
    monkeypatch.setattr(
        "lockean_lite.entry_diagnostic.fetch_official_vix_history",
        lambda: "fake-vix-csv",
    )
    monkeypatch.setattr(
        "lockean_lite.entry_diagnostic.read_spy_daily_evidence",
        lambda **kwargs: fake_spy_evidence,
    )
    monkeypatch.setattr(
        "lockean_lite.entry_diagnostic.read_cboe_vix_daily_evidence",
        lambda **kwargs: fake_vix_evidence,
    )
    monkeypatch.setattr(
        "lockean_lite.entry_diagnostic.create_openai_recommendation_model",
        lambda: object(),
    )
    monkeypatch.setattr(
        "lockean_lite.entry_diagnostic.StructuredAIRecommendationProvider",
        lambda **kwargs: object(),
    )
    monkeypatch.setattr(
        "lockean_lite.entry_diagnostic.LockeanAuthority",
        lambda **kwargs: object(),
    )
    monkeypatch.setattr(
        "lockean_lite.entry_diagnostic.read_paper_account_snapshot_from_environment",
        fake_account_provider,
    )

    def fake_autonomous_cycle(**kwargs):
        captured["account_snapshot_provider"] = (
            kwargs["account_snapshot_provider"]
        )
        return expected_result

    monkeypatch.setattr(
        "lockean_lite.entry_diagnostic.run_autonomous_trade_cycle",
        fake_autonomous_cycle,
    )

    result = run_live_entry_diagnostic(
        completed_through=date(2026, 9, 3),
        expiration=date(2026, 9, 18),
        maximum_allowed_loss=Decimal("150.00"),
        authorization_signing_key=b"test-signing-key",
    )

    assert result is expected_result
    assert (
        captured["account_snapshot_provider"]
        is fake_account_provider
    )


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
