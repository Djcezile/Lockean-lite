from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from lockean_lite.autonomous_cycle import (
    AutonomousTradeCycleResult,
)
from lockean_lite.production_runtime import (
    run_live_production_autonomous_cycle,
)


def test_live_runtime_passes_intraday_context_into_agent_cycle(monkeypatch):
    captured = {}
    fake_stock_client = object()
    fake_spy_evidence = object()
    fake_vix_evidence = object()
    intraday_context = {
        "intraday_status": "AVAILABLE",
        "intraday_return_15m_pct": "0.250",
        "intraday_direction_15m": "UP",
    }

    monkeypatch.setattr(
        "lockean_lite.production_runtime.load_alpaca_credentials_from_environment",
        lambda: SimpleNamespace(
            api_key="key",
            secret_key="secret",
        ),
    )

    class FakeStockHistoricalDataClient:
        def __new__(cls, api_key, secret_key):
            return fake_stock_client

    monkeypatch.setattr(
        "lockean_lite.production_runtime.StockHistoricalDataClient",
        FakeStockHistoricalDataClient,
    )

    monkeypatch.setattr(
        "lockean_lite.production_runtime.read_spy_daily_evidence",
        lambda **kwargs: fake_spy_evidence,
    )
    monkeypatch.setattr(
        "lockean_lite.production_runtime.read_cboe_vix_daily_evidence",
        lambda **kwargs: fake_vix_evidence,
    )

    def fake_intraday_reader(*, client):
        captured["intraday_client"] = client
        return intraday_context

    monkeypatch.setattr(
        "lockean_lite.production_runtime.read_spy_intraday_context",
        fake_intraday_reader,
    )

    def fake_cycle(**kwargs):
        captured["intraday_context"] = kwargs["intraday_context"]
        return AutonomousTradeCycleResult(
            status="NO_TRADE",
            reason="agent_declined_trade",
            diagnostics=("base",),
        )

    monkeypatch.setattr(
        "lockean_lite.production_runtime.run_production_autonomous_cycle",
        fake_cycle,
    )

    vix_source = SimpleNamespace(
        read=lambda: SimpleNamespace(
            csv_text="csv",
            mode="live",
            cache_age_seconds=0,
        )
    )

    result = run_live_production_autonomous_cycle(
        completed_through=date(2026, 9, 10),
        expiration=date(2026, 9, 18),
        maximum_allowed_loss=Decimal("150.00"),
        authorization_signing_key=b"test-key",
        vix_history_source=vix_source,
    )

    assert captured["intraday_client"] is fake_stock_client
    assert captured["intraday_context"] == intraday_context
    assert "intraday_context=available:alpaca_iex_minute" in result.diagnostics
    assert "vix_source=live:cache_age_seconds=0" in result.diagnostics
