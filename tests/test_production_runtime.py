from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from lockean_lite.production_runtime import (
    run_live_production_autonomous_cycle,
    run_production_autonomous_cycle,
)


def _spy_evidence():
    return SimpleNamespace(
        bars=(
            SimpleNamespace(
                close=Decimal("769.28"),
            ),
        )
    )


def test_production_runtime_composes_real_boundaries_with_same_lockean_policy(
    monkeypatch,
):
    captured = {}

    fake_trading_client = object()
    fake_option_client = object()
    fake_model = object()
    fake_recommendation_provider = object()
    fake_authority = object()
    fake_gateway = object()
    fake_quotes = ("trusted-quotes",)
    expected_result = object()

    monkeypatch.setenv(
        "ALPACA_API_KEY",
        "test-api-key",
    )
    monkeypatch.setenv(
        "ALPACA_SECRET_KEY",
        "test-secret-key",
    )

    monkeypatch.setattr(
        "lockean_lite.production_runtime.create_paper_trading_client_from_environment",
        lambda: fake_trading_client,
    )

    class FakeOptionHistoricalDataClient:
        def __init__(
            self,
            api_key,
            secret_key,
        ):
            captured["option_api_key"] = api_key
            captured["option_secret_key"] = secret_key

        def __new__(
            cls,
            api_key,
            secret_key,
        ):
            captured["option_api_key"] = api_key
            captured["option_secret_key"] = secret_key
            return fake_option_client

    monkeypatch.setattr(
        "lockean_lite.production_runtime.OptionHistoricalDataClient",
        FakeOptionHistoricalDataClient,
    )

    monkeypatch.setattr(
        "lockean_lite.production_runtime.create_openai_recommendation_model",
        lambda: fake_model,
    )

    def fake_recommendation_provider(
        *,
        proposal_id_provider,
        model_callable,
        maximum_allowed_loss,
    ):
        captured["recommendation_model"] = (
            model_callable
        )
        captured["ai_policy"] = (
            maximum_allowed_loss
        )

        return fake_recommendation_provider

    monkeypatch.setattr(
        "lockean_lite.production_runtime.StructuredAIRecommendationProvider",
        fake_recommendation_provider,
    )

    def fake_candidate_reader(
        *,
        trading_client,
        option_data_client,
        expiration,
        minimum_strike,
        maximum_strike,
    ):
        captured["candidate_trading_client"] = (
            trading_client
        )
        captured["candidate_option_client"] = (
            option_data_client
        )
        captured["expiration"] = expiration
        captured["minimum_strike"] = (
            minimum_strike
        )
        captured["maximum_strike"] = (
            maximum_strike
        )

        return fake_quotes

    monkeypatch.setattr(
        "lockean_lite.production_runtime.read_spy_call_candidate_quotes",
        fake_candidate_reader,
    )

    def fake_api_account_provider():
        return "account"

    monkeypatch.setattr(
        "lockean_lite.production_runtime.read_paper_account_snapshot_from_environment",
        fake_api_account_provider,
    )

    def fake_authority_constructor(
        *,
        maximum_allowed_loss,
        authorization_signing_key,
    ):
        captured["authority_policy"] = (
            maximum_allowed_loss
        )
        captured["authority_key"] = (
            authorization_signing_key
        )

        return fake_authority

    monkeypatch.setattr(
        "lockean_lite.production_runtime.LockeanAuthority",
        fake_authority_constructor,
    )

    def fake_gateway_constructor(
        *,
        client,
        signing_key,
    ):
        captured["gateway_client"] = client
        captured["gateway_key"] = signing_key

        return fake_gateway

    monkeypatch.setattr(
        "lockean_lite.production_runtime.PaperExecutionGateway",
        fake_gateway_constructor,
    )

    def fake_autonomous_cycle(**kwargs):
        captured["candidate_result"] = (
            kwargs[
                "candidate_quotes_provider"
            ]()
        )

        captured["cycle_recommendation_provider"] = (
            kwargs["recommendation_provider"]
        )

        captured["cycle_account_provider"] = (
            kwargs["account_snapshot_provider"]
        )

        captured["cycle_authority"] = (
            kwargs["authority"]
        )

        captured["cycle_gateway"] = (
            kwargs["execution_gateway"]
        )

        return expected_result

    monkeypatch.setattr(
        "lockean_lite.production_runtime.run_autonomous_trade_cycle",
        fake_autonomous_cycle,
    )

    result = run_production_autonomous_cycle(
        spy_evidence=_spy_evidence(),
        vix_evidence=object(),
        expiration=date(
            2026,
            9,
            18,
        ),
        maximum_allowed_loss=Decimal(
            "150.00"
        ),
        authorization_signing_key=(
            b"authority-test-key"
        ),
        proposal_id_provider=lambda: (
            "production-001"
        ),
    )

    assert result is expected_result

    assert captured["ai_policy"] == Decimal(
        "150.00"
    )

    assert captured[
        "authority_policy"
    ] == Decimal("150.00")

    assert captured[
        "authority_key"
    ] == b"authority-test-key"

    assert captured[
        "gateway_key"
    ] == b"authority-test-key"

    assert captured[
        "recommendation_model"
    ] is fake_model

    assert captured[
        "candidate_trading_client"
    ] is fake_trading_client

    assert captured[
        "candidate_option_client"
    ] is fake_option_client

    assert captured[
        "candidate_result"
    ] == fake_quotes

    assert captured[
        "minimum_strike"
    ] == Decimal("749")

    assert captured[
        "maximum_strike"
    ] == Decimal("789")

    assert captured[
        "cycle_recommendation_provider"
    ] is fake_recommendation_provider

    assert captured[
        "cycle_account_provider"
    ] is fake_api_account_provider

    assert captured[
        "cycle_authority"
    ] is fake_authority

    assert captured[
        "cycle_gateway"
    ] is fake_gateway


def test_production_runtime_rejects_missing_authority_signing_key():
    with pytest.raises(
        ValueError,
        match="authorization_signing_key_required",
    ):
        run_production_autonomous_cycle(
            spy_evidence=_spy_evidence(),
            vix_evidence=object(),
            expiration=date(
                2026,
                9,
                18,
            ),
            maximum_allowed_loss=Decimal(
                "150.00"
            ),
            authorization_signing_key=b"",
            proposal_id_provider=lambda: (
                "production-002"
            ),
        )


def test_live_production_runtime_builds_market_evidence_before_running_cycle(
    monkeypatch,
):
    captured = {}

    fake_credentials = SimpleNamespace(
        api_key="test-api-key",
        secret_key="test-secret-key",
    )

    fake_stock_client = object()
    fake_spy_evidence = object()
    fake_vix_evidence = object()
    expected_result = object()

    monkeypatch.setattr(
        "lockean_lite.production_runtime.load_alpaca_credentials_from_environment",
        lambda: fake_credentials,
    )

    class FakeStockHistoricalDataClient:
        def __new__(
            cls,
            api_key,
            secret_key,
        ):
            captured["stock_api_key"] = api_key
            captured["stock_secret_key"] = secret_key
            return fake_stock_client

    monkeypatch.setattr(
        "lockean_lite.production_runtime.StockHistoricalDataClient",
        FakeStockHistoricalDataClient,
    )

    monkeypatch.setattr(
        "lockean_lite.production_runtime.fetch_official_vix_history",
        lambda: "fake-vix-csv",
    )

    def fake_read_spy_daily_evidence(
        *,
        client,
        completed_through,
        start,
    ):
        captured["spy_client"] = client
        captured["completed_through"] = (
            completed_through
        )
        captured["start"] = start

        return fake_spy_evidence

    monkeypatch.setattr(
        "lockean_lite.production_runtime.read_spy_daily_evidence",
        fake_read_spy_daily_evidence,
    )

    def fake_read_vix_daily_evidence(
        *,
        csv_text,
        completed_through,
    ):
        captured["vix_csv_text"] = csv_text

        return fake_vix_evidence

    monkeypatch.setattr(
        "lockean_lite.production_runtime.read_cboe_vix_daily_evidence",
        fake_read_vix_daily_evidence,
    )

    def fake_run_production_cycle(**kwargs):
        captured["spy_evidence"] = (
            kwargs["spy_evidence"]
        )
        captured["vix_evidence"] = (
            kwargs["vix_evidence"]
        )

        return expected_result

    monkeypatch.setattr(
        "lockean_lite.production_runtime.run_production_autonomous_cycle",
        fake_run_production_cycle,
    )

    result = run_live_production_autonomous_cycle(
        completed_through=date(
            2026,
            9,
            2,
        ),
        expiration=date(
            2026,
            9,
            18,
        ),
        maximum_allowed_loss=Decimal(
            "150.00"
        ),
        authorization_signing_key=(
            b"authority-test-key"
        ),
    )

    assert result is expected_result

    assert captured[
        "stock_api_key"
    ] == "test-api-key"

    assert captured[
        "stock_secret_key"
    ] == "test-secret-key"

    assert captured[
        "spy_client"
    ] is fake_stock_client

    assert captured[
        "vix_csv_text"
    ] == "fake-vix-csv"

    assert captured[
        "spy_evidence"
    ] is fake_spy_evidence

    assert captured[
        "vix_evidence"
    ] is fake_vix_evidence


def test_live_production_runtime_rejects_missing_signing_key_before_external_evidence(
    monkeypatch,
):
    monkeypatch.setattr(
        "lockean_lite.production_runtime.load_alpaca_credentials_from_environment",
        lambda: pytest.fail(
            "credentials must not be loaded"
        ),
    )

    monkeypatch.setattr(
        "lockean_lite.production_runtime.fetch_official_vix_history",
        lambda: pytest.fail(
            "VIX evidence must not be fetched"
        ),
    )

    with pytest.raises(
        ValueError,
        match="authorization_signing_key_required",
    ):
        run_live_production_autonomous_cycle(
            completed_through=date(
                2026,
                9,
                2,
            ),
            expiration=date(
                2026,
                9,
                18,
            ),
            maximum_allowed_loss=Decimal(
                "150.00"
            ),
            authorization_signing_key=b"",
        )
