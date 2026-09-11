from decimal import Decimal

from lockean_lite.ai_recommendation_provider import (
    StructuredAIRecommendationProvider,
)
from lockean_lite.autonomous_cycle import (
    run_autonomous_trade_cycle,
)


def test_no_trade_cycle_logs_context_decision_and_rationale(monkeypatch):
    monkeypatch.setattr(
        "lockean_lite.autonomous_cycle.build_agent_market_context",
        lambda *, spy_evidence, vix_evidence, intraday_context=None: {
            "spy_close": "770.00",
            "trend": "PASS",
            "momentum": "FAIL",
            "breakout": "FAIL",
            "vix_close": "15.20",
            "volatility": "PASS",
            **(intraday_context or {}),
        },
    )

    provider = StructuredAIRecommendationProvider(
        proposal_id_provider=lambda: "observable-no-trade-001",
        model_callable=lambda prompt: """
        {
          "decision": "NO_TRADE",
          "symbol": null,
          "expiration": null,
          "buy_strike": null,
          "sell_strike": null,
          "contracts": null,
          "rationale": "Daily momentum is weak while the intraday tape is mixed."
        }
        """,
        maximum_allowed_loss=Decimal("150.00"),
    )

    result = run_autonomous_trade_cycle(
        spy_evidence=object(),
        vix_evidence=object(),
        intraday_context={
            "intraday_status": "AVAILABLE",
            "intraday_return_15m_pct": "0.125",
            "intraday_direction_15m": "UP",
        },
        candidate_quotes_provider=lambda: (),
        recommendation_provider=provider,
        account_snapshot_provider=lambda: object(),
        authority=object(),
        execution_gateway=object(),
    )

    assert result.status == "NO_TRADE"
    assert result.reason == "agent_declined_trade"
    assert "agent_decision=NO_TRADE" in result.diagnostics
    assert (
        "agent_rationale=Daily momentum is weak while the intraday tape is mixed."
        in result.diagnostics
    )

    context_lines = tuple(
        item
        for item in result.diagnostics
        if item.startswith("agent_context=")
    )

    assert len(context_lines) == 1
    assert "trend=PASS" in context_lines[0]
    assert "momentum=FAIL" in context_lines[0]
    assert "intraday_return_15m_pct=0.125" in context_lines[0]
    assert "intraday_direction_15m=UP" in context_lines[0]


def test_provider_bounds_multiline_rationale_for_safe_log_output():
    provider = StructuredAIRecommendationProvider(
        proposal_id_provider=lambda: "observable-no-trade-002",
        model_callable=lambda prompt: """
        {
          "decision": "NO_TRADE",
          "symbol": null,
          "expiration": null,
          "buy_strike": null,
          "sell_strike": null,
          "contracts": null,
          "rationale": "First line.\nSecond line."
        }
        """,
    )

    assert provider(()) is None
    assert provider.last_decision == "NO_TRADE"
    assert provider.last_decision_rationale == "First line. Second line."
