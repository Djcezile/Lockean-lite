from lockean_lite.ai_recommendation_provider import (
    build_recommendation_prompt,
)


def test_balanced_prompt_weighs_signals_without_hard_veto_or_trade_bias():
    prompt = build_recommendation_prompt(
        proposal_id="balanced-judgment-001",
        candidate_quotes=(),
        market_context={
            "trend": "PASS",
            "momentum": "PASS",
            "breakout": "FAIL",
            "volatility": "FAIL",
            "intraday_return_5m_pct": "0.112",
            "intraday_return_15m_pct": "0.323",
            "intraday_return_30m_pct": "0.444",
            "intraday_direction_5m": "UP",
            "intraday_direction_15m": "UP",
            "intraday_direction_30m": "UP",
        },
        activity_mode="balanced",
    )

    assert "BALANCED JUDGMENT" in prompt
    assert "not as independent hard vetoes" in prompt
    assert (
        "does not automatically require decision=NO_TRADE"
        in prompt
    )
    assert (
        "positive intraday momentum does not automatically require "
        "decision=TRADE"
        in prompt
    )
    assert "combined market evidence and candidate quality" in prompt

    # Balanced mode must remain neutral rather than inherit the
    # experiment-oriented activity bias of active_paper mode.
    assert "Prefer decision=TRADE" not in prompt
    assert "ACTIVE PAPER MODE" not in prompt

    # More nuanced AI judgment still grants no permission or execution power.
    assert "Do not return pricing, risk calculations" in prompt
    assert "permission decisions" in prompt
    assert "broker instructions" in prompt
    assert "authorization_receipt" not in prompt
