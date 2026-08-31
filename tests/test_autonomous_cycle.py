from datetime import date, datetime, timezone
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
from lockean_lite.market_entry_policy import (
    MarketEntryEvaluation,
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


def test_autonomous_cycle_stops_before_ai_and_broker_work_when_market_policy_fails(
    monkeypatch,
):
    candidate_calls = []
    recommendation_calls = []
    account_calls = []

    monkeypatch.setattr(
        "lockean_lite.autonomous_cycle.evaluate_market_entry_policy",
        lambda spy_evidence, vix_evidence: MarketEntryEvaluation(
            passed=False,
            reason="breakout_filter_failed",
        ),
    )

    result = run_autonomous_trade_cycle(
        spy_evidence=object(),
        vix_evidence=object(),
        candidate_quotes_provider=lambda: (
            candidate_calls.append(True)
        ),
        recommendation_provider=lambda candidates: (
            recommendation_calls.append(True)
        ),
        account_snapshot_provider=lambda: (
            account_calls.append(True)
        ),
        authority=object(),
        execution_gateway=object(),
    )

    assert result.status == "REJECTED"
    assert result.reason == "breakout_filter_failed"

    assert candidate_calls == []
    assert recommendation_calls == []
    assert account_calls == []


def test_autonomous_cycle_lets_ai_choose_structure_but_lockean_sets_proposal_debit(
    monkeypatch,
):
    observed = {}

    monkeypatch.setattr(
        "lockean_lite.autonomous_cycle.evaluate_market_entry_policy",
        lambda spy_evidence, vix_evidence: MarketEntryEvaluation(
            passed=True,
            reason="entry_conditions_satisfied",
        ),
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
        spy_evidence=object(),
        vix_evidence=object(),
        candidate_quotes_provider=_candidate_quotes,
        recommendation_provider=lambda candidates: _recommendation(),
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

    monkeypatch.setattr(
        "lockean_lite.autonomous_cycle.evaluate_market_entry_policy",
        lambda spy_evidence, vix_evidence: MarketEntryEvaluation(
            passed=True,
            reason="entry_conditions_satisfied",
        ),
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
        spy_evidence=object(),
        vix_evidence=object(),
        candidate_quotes_provider=_candidate_quotes,
        recommendation_provider=lambda candidates: (
            missing_contract_recommendation
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

    monkeypatch.setattr(
        "lockean_lite.autonomous_cycle.evaluate_market_entry_policy",
        lambda spy_evidence, vix_evidence: MarketEntryEvaluation(
            passed=True,
            reason="entry_conditions_satisfied",
        ),
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
        spy_evidence=object(),
        vix_evidence=object(),
        candidate_quotes_provider=_candidate_quotes,
        recommendation_provider=lambda candidates: _recommendation(),
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