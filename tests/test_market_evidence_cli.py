from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

from lockean_lite.market_evidence_cli import (
    main,
    run_market_evidence_cli,
)


COMPLETED_THROUGH = date(
    2026,
    8,
    31,
)


def test_cli_reuses_credentials_and_read_only_demo(
    monkeypatch,
):
    calls = []

    credentials = SimpleNamespace(
        api_key="paper-key",
        secret_key="paper-secret",
    )

    monkeypatch.setattr(
        "lockean_lite.market_evidence_cli.load_alpaca_credentials_from_environment",
        lambda: credentials,
    )

    def stock_client_factory(
        api_key,
        secret_key,
    ):
        calls.append(
            (
                "stock_client",
                api_key,
                secret_key,
            )
        )
        return "stock-client"

    monkeypatch.setattr(
        "lockean_lite.market_evidence_cli.StockHistoricalDataClient",
        stock_client_factory,
    )

    monkeypatch.setattr(
        "lockean_lite.market_evidence_cli.fetch_official_vix_history",
        lambda: (
            calls.append(
                (
                    "vix",
                    "official-cboe",
                )
            )
            or "vix-csv"
        ),
    )

    def demo_runner(**kwargs):
        calls.append(
            (
                "demo",
                kwargs,
            )
        )
        return "LOCKEAN DECISION REPORT"

    monkeypatch.setattr(
        "lockean_lite.market_evidence_cli.run_market_evidence_demo",
        demo_runner,
    )

    output = run_market_evidence_cli(
        completed_through=COMPLETED_THROUGH,
    )

    assert output == (
        "LOCKEAN DECISION REPORT"
    )

    assert calls[0] == (
        "vix",
        "official-cboe",
    )

    assert calls[1] == (
        "stock_client",
        "paper-key",
        "paper-secret",
    )

    assert calls[2][0] == "demo"

    assert calls[2][1] == {
        "stock_client": "stock-client",
        "vix_csv_text": "vix-csv",
        "completed_through": COMPLETED_THROUGH,
        "start": datetime(
            2025,
            1,
            1,
            tzinfo=timezone.utc,
        ),
    }


def test_cli_missing_credentials_fails_closed_before_external_evidence(
    monkeypatch,
):
    def missing_credentials():
        raise ValueError(
            "missing_alpaca_credentials: ALPACA_API_KEY"
        )

    monkeypatch.setattr(
        "lockean_lite.market_evidence_cli.load_alpaca_credentials_from_environment",
        missing_credentials,
    )

    monkeypatch.setattr(
        "lockean_lite.market_evidence_cli.fetch_official_vix_history",
        lambda: pytest.fail(
            "VIX retrieval must not occur"
        ),
    )

    monkeypatch.setattr(
        "lockean_lite.market_evidence_cli.run_market_evidence_demo",
        lambda **kwargs: pytest.fail(
            "demo must not run"
        ),
    )

    with pytest.raises(
        ValueError,
        match=(
            "missing_alpaca_credentials: "
            "ALPACA_API_KEY"
        ),
    ):
        run_market_evidence_cli(
            completed_through=COMPLETED_THROUGH,
        )


def test_cli_missing_official_vix_fails_closed_without_substitute(
    monkeypatch,
):
    monkeypatch.setattr(
        "lockean_lite.market_evidence_cli.load_alpaca_credentials_from_environment",
        lambda: SimpleNamespace(
            api_key="paper-key",
            secret_key="paper-secret",
        ),
    )

    def unavailable_vix():
        raise ValueError(
            "vix_evidence_unavailable"
        )

    monkeypatch.setattr(
        "lockean_lite.market_evidence_cli.fetch_official_vix_history",
        unavailable_vix,
    )

    monkeypatch.setattr(
        "lockean_lite.market_evidence_cli.run_market_evidence_demo",
        lambda **kwargs: pytest.fail(
            "demo must not run with missing VIX evidence"
        ),
    )

    with pytest.raises(
        ValueError,
        match="vix_evidence_unavailable",
    ):
        run_market_evidence_cli(
            completed_through=COMPLETED_THROUGH,
        )


def test_cli_main_explains_fail_closed_reason(
    monkeypatch,
    capsys,
):
    monkeypatch.setattr(
        "lockean_lite.market_evidence_cli.run_market_evidence_cli",
        lambda **kwargs: (
            pytest.fail(
                "successful demo must not be produced"
            )
        ),
    )

    def failed_runner(**kwargs):
        raise ValueError(
            "vix_completed_session_missing"
        )

    monkeypatch.setattr(
        "lockean_lite.market_evidence_cli.run_market_evidence_cli",
        failed_runner,
    )

    exit_code = main(
        [
            "--completed-through",
            "2026-08-31",
        ]
    )

    output = capsys.readouterr().out

    assert exit_code == 1

    assert (
        "LOCKEAN DEMO FAILED CLOSED"
        in output
    )

    assert (
        "REASON: vix_completed_session_missing"
        in output
    )

    assert (
        "BROKER ORDER SUBMITTED: NO"
        in output
    )


def test_cli_has_no_execution_authority_dependencies():
    import lockean_lite.market_evidence_cli as cli

    forbidden_names = (
        "LockeanAuthority",
        "PaperExecutionGateway",
        "StructuredAIRecommendationProvider",
        "AuthorizationReceipt",
        "execute_authorized_paper_order",
        "issue_authorization_receipt",
    )

    for name in forbidden_names:
        assert not hasattr(
            cli,
            name,
        )