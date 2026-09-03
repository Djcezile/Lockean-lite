# tests/test_live_agent_demo.py

from datetime import date
from decimal import Decimal

from lockean_lite.live_agent_demo import (
    main,
    render_live_agent_demo,
    run_live_agent_demo,
    run_real_live_agent_demo,
)
from types import SimpleNamespace


def test_live_agent_demo_renders_no_trade_without_execution_language():
    spy_evidence = SimpleNamespace(
        evidence_id="alpaca-spy-2026-09-02",
        as_of="2026-09-02T20:00:00+00:00",
    )

    vix_evidence = SimpleNamespace(
        evidence_id="cboe-vix-2026-09-02",
    )

    market_context = {
        "spy_close": "765.13",
        "trend": "PASS",
        "momentum": "PASS",
        "breakout": "FAIL",
        "vix_close": "15.200000",
        "volatility": "FAIL",
    }

    output = render_live_agent_demo(
        spy_evidence=spy_evidence,
        vix_evidence=vix_evidence,
        candidate_count=41,
        market_context=market_context,
        recommendation=None,
    )

    assert "LOCKEAN LIVE AGENT DEMO" in output

    assert (
        "SPY EVIDENCE: "
        "alpaca-spy-2026-09-02"
    ) in output

    assert (
        "VIX EVIDENCE: "
        "cboe-vix-2026-09-02"
    ) in output

    assert "CANDIDATE OPTIONS: 41" in output

    assert "trend: PASS" in output
    assert "breakout: FAIL" in output
    assert "volatility: FAIL" in output

    assert "AGENT DECISION: NO_TRADE" in output

    assert "LOCKEAN AUTHORITY INVOKED: NO" in output
    assert "EXECUTION GATEWAY INVOKED: NO" in output
    assert "BROKER ORDER SUBMITTED: NO" in output

def test_live_agent_demo_renders_trade_proposal_but_stops_before_execution():
    spy_evidence = SimpleNamespace(
        evidence_id="alpaca-spy-2026-09-02",
        as_of="2026-09-02T20:00:00+00:00",
    )

    vix_evidence = SimpleNamespace(
        evidence_id="cboe-vix-2026-09-02",
    )

    market_context = {
        "spy_close": "765.13",
        "trend": "PASS",
        "momentum": "PASS",
        "breakout": "FAIL",
        "vix_close": "15.200000",
        "volatility": "FAIL",
    }

    recommendation = SimpleNamespace(
        symbol="SPY",
        expiration="2026-09-18",
        buy_strike="782",
        sell_strike="785",
        contracts=1,
    )

    output = render_live_agent_demo(
        spy_evidence=spy_evidence,
        vix_evidence=vix_evidence,
        candidate_count=41,
        market_context=market_context,
        recommendation=recommendation,
    )

    assert "AGENT DECISION: TRADE" in output
    assert "SYMBOL: SPY" in output
    assert "EXPIRATION: 2026-09-18" in output
    assert "BUY STRIKE: 782" in output
    assert "SELL STRIKE: 785" in output
    assert "CONTRACTS: 1" in output

    assert "LOCKEAN AUTHORITY INVOKED: NO" in output
    assert "EXECUTION GATEWAY INVOKED: NO" in output
    assert "BROKER ORDER SUBMITTED: NO" in output

def test_live_agent_demo_composes_candidates_context_and_ai_recommendation(
    monkeypatch,
):
    spy_evidence = SimpleNamespace(
        evidence_id="alpaca-spy-2026-09-02",
        as_of="2026-09-02T20:00:00+00:00",
        bars=(
            SimpleNamespace(
                close=Decimal("765.13"),
            ),
        ),
    )

    vix_evidence = SimpleNamespace(
        evidence_id="cboe-vix-2026-09-02",
        bars=(
            SimpleNamespace(
                close=Decimal("15.200000"),
            ),
        ),
    )

    candidate_quotes = (
        object(),
        object(),
        object(),
    )

    captured = {}

    def candidate_quotes_provider():
        captured["candidate_provider_called"] = True
        return candidate_quotes

    expected_context = {
        "spy_close": "765.13",
        "trend": "PASS",
        "momentum": "PASS",
        "breakout": "FAIL",
        "vix_close": "15.200000",
        "volatility": "FAIL",
    }

    def fake_market_context_builder(
        *,
        spy_evidence,
        vix_evidence,
    ):
        captured["context_spy"] = spy_evidence
        captured["context_vix"] = vix_evidence

        return expected_context

    recommendation = SimpleNamespace(
        symbol="SPY",
        expiration="2026-09-18",
        buy_strike="782",
        sell_strike="785",
        contracts=1,
    )

    def recommendation_provider(
        quotes,
        *,
        market_context,
    ):
        captured["recommendation_quotes"] = quotes
        captured["recommendation_context"] = (
            market_context
        )

        return recommendation

    output = run_live_agent_demo(
        spy_evidence=spy_evidence,
        vix_evidence=vix_evidence,
        candidate_quotes_provider=(
            candidate_quotes_provider
        ),
        recommendation_provider=(
            recommendation_provider
        ),
        market_context_builder=(
            fake_market_context_builder
        ),
    )

    assert captured[
        "candidate_provider_called"
    ] is True

    assert captured[
        "context_spy"
    ] is spy_evidence

    assert captured[
        "context_vix"
    ] is vix_evidence

    assert captured[
        "recommendation_quotes"
    ] is candidate_quotes

    assert captured[
        "recommendation_context"
    ] == expected_context

    assert "CANDIDATE OPTIONS: 3" in output
    assert "AGENT DECISION: TRADE" in output
    assert "BUY STRIKE: 782" in output
    assert "SELL STRIKE: 785" in output

    assert "LOCKEAN AUTHORITY INVOKED: NO" in output
    assert "EXECUTION GATEWAY INVOKED: NO" in output
    assert "BROKER ORDER SUBMITTED: NO" in output

def test_live_agent_demo_uses_shared_market_context_builder_by_default(
    monkeypatch,
):
    spy_evidence = SimpleNamespace(
        evidence_id="alpaca-spy-2026-09-02",
        as_of="2026-09-02T20:00:00+00:00",
        bars=(
            SimpleNamespace(
                close=Decimal("765.13"),
            ),
        ),
    )

    vix_evidence = SimpleNamespace(
        evidence_id="cboe-vix-2026-09-02",
        bars=(
            SimpleNamespace(
                close=Decimal("15.200000"),
            ),
        ),
    )

    expected_context = {
        "spy_close": "765.13",
        "trend": "PASS",
        "momentum": "PASS",
        "breakout": "FAIL",
        "vix_close": "15.200000",
        "volatility": "FAIL",
    }

    captured = {}

    def fake_context_builder(
        *,
        spy_evidence,
        vix_evidence,
    ):
        captured["spy"] = spy_evidence
        captured["vix"] = vix_evidence

        return expected_context

    monkeypatch.setattr(
        "lockean_lite.live_agent_demo.build_agent_market_context",
        fake_context_builder,
    )

    def recommendation_provider(
        candidates,
        *,
        market_context,
    ):
        captured["market_context"] = market_context
        return None

    output = run_live_agent_demo(
        spy_evidence=spy_evidence,
        vix_evidence=vix_evidence,
        candidate_quotes_provider=lambda: (
            object(),
            object(),
        ),
        recommendation_provider=(
            recommendation_provider
        ),
    )

    assert captured["spy"] is spy_evidence
    assert captured["vix"] is vix_evidence
    assert captured["market_context"] == expected_context

    assert "CANDIDATE OPTIONS: 2" in output
    assert "AGENT DECISION: NO_TRADE" in output
    assert "BROKER ORDER SUBMITTED: NO" in output


def test_real_live_agent_demo_composes_read_only_market_and_ai_boundaries(
    monkeypatch,
):
    captured = {}

    fake_credentials = SimpleNamespace(
        api_key="test-api-key",
        secret_key="test-secret-key",
    )

    fake_stock_client = object()
    fake_option_client = object()
    fake_trading_client = object()

    fake_spy_evidence = SimpleNamespace(
        evidence_id="alpaca-spy-real",
        as_of="2026-09-02T20:00:00+00:00",
        bars=(
            SimpleNamespace(
                close=Decimal("765.13"),
            ),
        ),
    )

    fake_vix_evidence = SimpleNamespace(
        evidence_id="cboe-vix-real",
        bars=(
            SimpleNamespace(
                close=Decimal("15.20"),
            ),
        ),
    )

    fake_quotes = (
        object(),
        object(),
        object(),
    )

    fake_model = object()
    fake_provider = object()

    monkeypatch.setattr(
        "lockean_lite.live_agent_demo.load_alpaca_credentials_from_environment",
        lambda: fake_credentials,
    )

    class FakeStockHistoricalDataClient:
        def __new__(
            cls,
            api_key,
            secret_key,
        ):
            captured["stock_credentials"] = (
                api_key,
                secret_key,
            )
            return fake_stock_client

    class FakeOptionHistoricalDataClient:
        def __new__(
            cls,
            api_key,
            secret_key,
        ):
            captured["option_credentials"] = (
                api_key,
                secret_key,
            )
            return fake_option_client

    monkeypatch.setattr(
        "lockean_lite.live_agent_demo.StockHistoricalDataClient",
        FakeStockHistoricalDataClient,
    )

    monkeypatch.setattr(
        "lockean_lite.live_agent_demo.OptionHistoricalDataClient",
        FakeOptionHistoricalDataClient,
    )

    monkeypatch.setattr(
        "lockean_lite.live_agent_demo.create_paper_trading_client_from_environment",
        lambda: fake_trading_client,
    )

    monkeypatch.setattr(
        "lockean_lite.live_agent_demo.fetch_official_vix_history",
        lambda: "fake-vix-csv",
    )

    def fake_read_spy(
        *,
        client,
        completed_through,
        start,
    ):
        captured["spy_client"] = client
        captured["completed_through"] = (
            completed_through
        )
        captured["history_start"] = start

        return fake_spy_evidence

    monkeypatch.setattr(
        "lockean_lite.live_agent_demo.read_spy_daily_evidence",
        fake_read_spy,
    )

    def fake_read_vix(
        *,
        csv_text,
        completed_through,
    ):
        captured["vix_csv"] = csv_text
        return fake_vix_evidence

    monkeypatch.setattr(
        "lockean_lite.live_agent_demo.read_cboe_vix_daily_evidence",
        fake_read_vix,
    )

    def fake_read_quotes(
        *,
        trading_client,
        option_data_client,
        expiration,
        minimum_strike,
        maximum_strike,
    ):
        captured["quote_trading_client"] = (
            trading_client
        )
        captured["quote_option_client"] = (
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
        "lockean_lite.live_agent_demo.read_spy_call_candidate_quotes",
        fake_read_quotes,
    )

    monkeypatch.setattr(
        "lockean_lite.live_agent_demo.create_openai_recommendation_model",
        lambda: fake_model,
    )

    def fake_provider_constructor(
        *,
        proposal_id_provider,
        model_callable,
        maximum_allowed_loss,
    ):
        captured["model"] = model_callable
        captured["maximum_allowed_loss"] = (
            maximum_allowed_loss
        )

        return fake_provider

    monkeypatch.setattr(
        "lockean_lite.live_agent_demo.StructuredAIRecommendationProvider",
        fake_provider_constructor,
    )

    expected_output = "judge-facing-output"

    def fake_run_live_agent_demo(**kwargs):
        captured["run_spy"] = kwargs[
            "spy_evidence"
        ]
        captured["run_vix"] = kwargs[
            "vix_evidence"
        ]
        captured["quotes"] = kwargs[
            "candidate_quotes_provider"
        ]()
        captured["provider"] = kwargs[
            "recommendation_provider"
        ]

        return expected_output

    monkeypatch.setattr(
        "lockean_lite.live_agent_demo.run_live_agent_demo",
        fake_run_live_agent_demo,
    )

    result = run_real_live_agent_demo(
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
        proposal_id_provider=lambda: (
            "demo-001"
        ),
    )

    assert result == expected_output

    assert captured["stock_credentials"] == (
        "test-api-key",
        "test-secret-key",
    )

    assert captured["option_credentials"] == (
        "test-api-key",
        "test-secret-key",
    )

    assert captured["spy_client"] is fake_stock_client
    assert captured["vix_csv"] == "fake-vix-csv"

    assert (
        captured["quote_trading_client"]
        is fake_trading_client
    )

    assert (
        captured["quote_option_client"]
        is fake_option_client
    )

    assert captured[
        "minimum_strike"
    ] == Decimal("745")

    assert captured[
        "maximum_strike"
    ] == Decimal("785")

    assert captured["model"] is fake_model

    assert captured[
        "maximum_allowed_loss"
    ] == Decimal("150.00")

    assert captured[
        "run_spy"
    ] is fake_spy_evidence

    assert captured[
        "run_vix"
    ] is fake_vix_evidence

    assert captured["quotes"] is fake_quotes
    assert captured["provider"] is fake_provider

def test_live_agent_demo_cli_runs_read_only_real_demo(
    monkeypatch,
    capsys,
):
    captured = {}

    def fake_run_real_live_agent_demo(
        *,
        completed_through,
        expiration,
        maximum_allowed_loss,
        proposal_id_provider=None,
        strike_window=Decimal("20"),
    ):
        captured["completed_through"] = (
            completed_through
        )
        captured["expiration"] = expiration
        captured["maximum_allowed_loss"] = (
            maximum_allowed_loss
        )

        return (
            "LOCKEAN LIVE AGENT DEMO\n"
            "AGENT DECISION: NO_TRADE\n"
            "BROKER ORDER SUBMITTED: NO"
        )

    monkeypatch.setattr(
        "lockean_lite.live_agent_demo.run_real_live_agent_demo",
        fake_run_real_live_agent_demo,
    )

    result = main(
        [
            "--completed-through",
            "2026-09-02",
            "--expiration",
            "2026-09-18",
        ]
    )

    output = capsys.readouterr().out

    assert result == 0

    assert captured[
        "completed_through"
    ] == date(
        2026,
        9,
        2,
    )

    assert captured[
        "expiration"
    ] == date(
        2026,
        9,
        18,
    )

    assert captured[
        "maximum_allowed_loss"
    ] == Decimal("150.00")

    assert "LOCKEAN LIVE AGENT DEMO" in output
    assert "AGENT DECISION: NO_TRADE" in output
    assert "BROKER ORDER SUBMITTED: NO" in output