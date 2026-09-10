from types import SimpleNamespace

from lockean_lite.autonomous_cycle import (
    run_autonomous_trade_cycle,
)


def test_portfolio_policy_rejects_before_evidence_authority_or_broker(monkeypatch):
    proposal = object()
    recommendation = SimpleNamespace(contracts=1)
    policy_calls = []

    monkeypatch.setattr(
        "lockean_lite.autonomous_cycle.build_agent_market_context",
        lambda **kwargs: {},
    )
    monkeypatch.setattr(
        "lockean_lite.autonomous_cycle.build_trade_proposal_from_recommendation",
        lambda **kwargs: proposal,
    )

    def policy_checker(actual_proposal, candidate_quotes):
        policy_calls.append((actual_proposal, candidate_quotes))
        return SimpleNamespace(
            allowed=False,
            reason="same_structure_concentration_limit_reached",
        )

    result = run_autonomous_trade_cycle(
        spy_evidence=object(),
        vix_evidence=object(),
        candidate_quotes_provider=lambda: ("quote",),
        recommendation_provider=lambda quotes, market_context: recommendation,
        account_snapshot_provider=lambda: (_ for _ in ()).throw(
            AssertionError("account snapshot must not be read after policy rejection")
        ),
        authority=object(),
        execution_gateway=object(),
        proposal_policy_checker=policy_checker,
    )

    assert result.status == "REJECTED"
    assert result.reason == "same_structure_concentration_limit_reached"
    assert policy_calls == [(proposal, ("quote",))]
