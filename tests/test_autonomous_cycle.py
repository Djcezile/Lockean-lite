from datetime import (
    date,
    datetime,
    timedelta,
    timezone,
)
from lockean_lite.market_evidence import (
    MarketBar,
    MarketEvidence,
)
from decimal import Decimal

from lockean_lite.application_workflow import (
    TradeDecisionCycleResult,
)
from lockean_lite.autonomous_cycle import (
    run_autonomous_trade_cycle,
)
from lockean_lite.evidence_validation import (
    EvidenceValidationResult,
    ValidatedMarketEvidence,
)
from lockean_lite.option_quote_snapshot import (
    OptionQuoteSnapshot,
)
from lockean_lite.paper_account_snapshot import (
    PaperAccountSnapshot,
)
from lockean_lite.trade_recommendation import (
    SpreadRecommendation,
)


AS_OF = datetime(
    2026,
    8,
    28,
    20,
    0,
    tzinfo=timezone.utc,
)

QUOTE_TIME = datetime(
    2026,
    8,
    28,
    19,
    59,
    59,
    tzinfo=timezone.utc,
)


def _quote(
    *,
    strike,
    bid,
    ask,
):
    strike_decimal = Decimal(str(strike))

    return OptionQuoteSnapshot(
        contract_symbol=(
            f"SPY260918C"
            f"{int(strike_decimal * 1000):08d}"
        ),
        underlying_symbol="SPY",
        option_type="call",
        strike=strike_decimal,
        expiration=date(2026, 9, 18),
        bid_price=Decimal(str(bid)),
        ask_price=Decimal(str(ask)),
        quote_timestamp=QUOTE_TIME,
        source="alpaca",
    )


def _candidate_quotes():
    return (
        _quote(
            strike=782,
            bid="2.96",
            ask="3.03",
        ),
        _quote(
            strike=787,
            bid="1.75",
            ask="1.76",
        ),
    )


def _recommendation():
    return SpreadRecommendation(
        proposal_id="autonomous-001",
        symbol="SPY",
        expiration=date(2026, 9, 18),
        buy_strike=Decimal("782"),
        sell_strike=Decimal("787"),
        contracts=1,
    )


def _account():
    return PaperAccountSnapshot(
        status="ACTIVE",
        currency="USD",
        trading_blocked=False,
        options_buying_power=Decimal("1000"),
        options_approved_level=3,
        options_trading_level=3,
    )

def _agent_market_evidence():
    start = datetime(
        2026,
        1,
        1,
        21,
        0,
        tzinfo=timezone.utc,
    )

    spy_closes = (
        [Decimal("700")] * 150
        + [Decimal("760")] * 49
        + [Decimal("765")]
    )

    spy_bars = tuple(
        MarketBar(
            timestamp=(
                start
                + timedelta(days=index)
            ),
            open=close,
            high=(
                close + Decimal("10")
                if index < 199
                else close + Decimal("1")
            ),
            low=close - Decimal("1"),
            close=close,
            volume=1_000_000,
        )
        for index, close in enumerate(
            spy_closes
        )
    )

    spy_evidence = MarketEvidence(
        evidence_id="spy-agent-context",
        symbol="SPY",
        as_of=spy_bars[-1].timestamp,
        source="alpaca",
        bars=spy_bars,
    )

    vix_closes = (
        [Decimal("15.20")] * 20
    )

    vix_bars = tuple(
        MarketBar(
            timestamp=(
                spy_bars[-20 + index].timestamp
            ),
            open=close,
            high=close,
            low=close,
            close=close,
            volume=1,
        )
        for index, close in enumerate(
            vix_closes
        )
    )

    vix_evidence = MarketEvidence(
        evidence_id="vix-agent-context",
        symbol="VIX",
        as_of=spy_evidence.as_of,
        source="cboe",
        bars=vix_bars,
    )

    return spy_evidence, vix_evidence

def test_autonomous_cycle_passes_real_market_signal_context_to_agent(
    monkeypatch,
):
    captured = {}

    spy_evidence, vix_evidence = (
        _agent_market_evidence()
    )

    missing_contract_recommendation = (
        SpreadRecommendation(
            proposal_id="autonomous-pivot-002",
            symbol="SPY",
            expiration=date(2026, 9, 18),
            buy_strike=Decimal("782"),
            sell_strike=Decimal("788"),
            contracts=1,
        )
    )

    def recommendation_provider(
        candidates,
        *,
        market_context,
    ):
        captured["market_context"] = (
            market_context
        )

        return missing_contract_recommendation

    result = run_autonomous_trade_cycle(
        spy_evidence=spy_evidence,
        vix_evidence=vix_evidence,
        candidate_quotes_provider=(
            _candidate_quotes
        ),
        recommendation_provider=(
            recommendation_provider
        ),
        account_snapshot_provider=_account,
        authority=object(),
        execution_gateway=object(),
    )

    assert result.status == "REJECTED"
    assert (
        result.reason
        == "recommended_option_quote_missing"
    )

    assert captured["market_context"] == {
        "spy_close": "765",
        "trend": "PASS",
        "momentum": "FAIL",
        "breakout": "FAIL",
        "vix_close": "15.20",
        "volatility": "FAIL",
    }


def test_autonomous_cycle_allows_agent_to_evaluate_when_old_market_signal_fails(
    monkeypatch,
):
    candidate_calls = []
    recommendation_calls = []
    account_calls = []

    spy_evidence, vix_evidence = (
    _agent_market_evidence()
)

    missing_contract_recommendation = SpreadRecommendation(
        proposal_id="autonomous-pivot-001",
        symbol="SPY",
        expiration=date(2026, 9, 18),
        buy_strike=Decimal("782"),
        sell_strike=Decimal("788"),
        contracts=1,
    )

    def candidate_provider():
        candidate_calls.append(True)
        return _candidate_quotes()

    def recommendation_provider(
        candidates,
        *,
        market_context,
    ):
        recommendation_calls.append(candidates)
        return missing_contract_recommendation

    result = run_autonomous_trade_cycle(
        spy_evidence=spy_evidence,
        vix_evidence=vix_evidence,
        candidate_quotes_provider=candidate_provider,
        recommendation_provider=recommendation_provider,
        account_snapshot_provider=lambda: (
            account_calls.append(True)
        ),
        authority=object(),
        execution_gateway=object(),
    )

    assert result.status == "REJECTED"
    assert (
        result.reason
        == "recommended_option_quote_missing"
    )

    assert candidate_calls == [True]
    assert len(recommendation_calls) == 1
    assert account_calls == []


def test_autonomous_cycle_lets_ai_choose_structure_but_lockean_sets_proposal_debit(
    monkeypatch,
):
    observed = {}

    spy_evidence, vix_evidence = (
    _agent_market_evidence()
)

    validated = ValidatedMarketEvidence(
        proposal_fingerprint="fingerprint",
        spy_evidence_id="spy-real",
        vix_evidence_id="vix-real",
        as_of=AS_OF,
        spy_source="alpaca",
        vix_source="cboe",
    )

    def fake_validate(
        *,
        proposal,
        spy_evidence,
        vix_evidence,
    ):
        observed["validated_proposal"] = proposal

        return EvidenceValidationResult(
            accepted=True,
            reason="evidence_validated",
            validated_evidence=validated,
        )

    monkeypatch.setattr(
        "lockean_lite.autonomous_cycle.validate_market_evidence_for_proposal",
        fake_validate,
    )

    def fake_run_trade_decision_cycle(
        *,
        proposal,
        account_snapshot,
        evidence_validation_result,
        authority,
        execution_gateway,
    ):
        observed["workflow_proposal"] = proposal
        observed["account"] = account_snapshot

        return TradeDecisionCycleResult(
            status="SUBMITTED",
            reason="paper_order_submitted",
        )

    monkeypatch.setattr(
        "lockean_lite.autonomous_cycle.run_trade_decision_cycle",
        fake_run_trade_decision_cycle,
    )

    result = run_autonomous_trade_cycle(
        spy_evidence=spy_evidence,
        vix_evidence=vix_evidence,
        candidate_quotes_provider=_candidate_quotes,
        recommendation_provider=(
    lambda candidates, *, market_context: (
        _recommendation()
    )
),
        account_snapshot_provider=_account,
        authority=object(),
        execution_gateway=object(),
    )

    assert result.status == "SUBMITTED"
    assert result.reason == "paper_order_submitted"

    proposal = observed["workflow_proposal"]

    assert proposal.legs[0].strike == Decimal("782")
    assert proposal.legs[1].strike == Decimal("787")

    assert proposal.net_debit == Decimal("1.28")


def test_autonomous_cycle_fails_closed_when_ai_recommendation_cannot_be_resolved(
    monkeypatch,
):
    account_calls = []

    spy_evidence, vix_evidence = (
    _agent_market_evidence()
)

    missing_contract_recommendation = SpreadRecommendation(
        proposal_id="autonomous-002",
        symbol="SPY",
        expiration=date(2026, 9, 18),
        buy_strike=Decimal("782"),
        sell_strike=Decimal("788"),
        contracts=1,
    )

    result = run_autonomous_trade_cycle(
        spy_evidence=spy_evidence,
        vix_evidence=vix_evidence,
        candidate_quotes_provider=_candidate_quotes,
        recommendation_provider=(
    lambda candidates, *, market_context: (
        missing_contract_recommendation
    )
),
        account_snapshot_provider=lambda: (
            account_calls.append(True)
        ),
        authority=object(),
        execution_gateway=object(),
    )

    assert result.status == "REJECTED"
    assert (
        result.reason
        == "recommended_option_quote_missing"
    )

    assert account_calls == []


def test_autonomous_cycle_stops_before_account_and_execution_when_evidence_binding_fails(
    monkeypatch,
):
    account_calls = []
    workflow_calls = []

    spy_evidence, vix_evidence = (
    _agent_market_evidence()
)

    monkeypatch.setattr(
        "lockean_lite.autonomous_cycle.validate_market_evidence_for_proposal",
        lambda **kwargs: EvidenceValidationResult(
            accepted=False,
            reason="evidence_as_of_mismatch",
        ),
    )

    monkeypatch.setattr(
        "lockean_lite.autonomous_cycle.run_trade_decision_cycle",
        lambda **kwargs: workflow_calls.append(True),
    )

    result = run_autonomous_trade_cycle(
        spy_evidence=spy_evidence,
        vix_evidence=vix_evidence,
        candidate_quotes_provider=_candidate_quotes,
        recommendation_provider=(
    lambda candidates, *, market_context: (
        _recommendation()
    )
),
        account_snapshot_provider=lambda: (
            account_calls.append(True)
        ),
        authority=object(),
        execution_gateway=object(),
    )

    assert result.status == "REJECTED"
    assert result.reason == "evidence_as_of_mismatch"

    assert account_calls == []
    assert workflow_calls == []

def test_autonomous_cycle_allows_agent_to_choose_no_trade(
    monkeypatch,
):
    spy_evidence, vix_evidence = (
        _agent_market_evidence()
    )

    account_calls = []
    workflow_calls = []

    monkeypatch.setattr(
        "lockean_lite.autonomous_cycle.run_trade_decision_cycle",
        lambda **kwargs: workflow_calls.append(True),
    )

    result = run_autonomous_trade_cycle(
        spy_evidence=spy_evidence,
        vix_evidence=vix_evidence,
        candidate_quotes_provider=(
            _candidate_quotes
        ),
        recommendation_provider=(
            lambda candidates, *, market_context: None
        ),
        account_snapshot_provider=lambda: (
            account_calls.append(True)
        ),
        authority=object(),
        execution_gateway=object(),
    )

    assert result.status == "NO_TRADE"
    assert result.reason == "agent_declined_trade"

    assert account_calls == []
    assert workflow_calls == []