from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from lockean_lite.evidence_validation import (
    ValidatedMarketEvidence,
    validate_market_evidence_for_proposal,
)
from lockean_lite.market_entry_policy import MarketEntryEvaluation
from lockean_lite.market_evidence import MarketBar, MarketEvidence
from lockean_lite.option_leg import OptionLeg
from lockean_lite.proposal_fingerprint import fingerprint_trade_proposal
from lockean_lite.trade_proposal import TradeProposal


BASE_AS_OF = datetime(
    2026,
    8,
    28,
    20,
    0,
    tzinfo=timezone.utc,
)


def _proposal():
    buy_leg = OptionLeg(
        option_type="call",
        strike=Decimal("500"),
        expiration=date(2026, 9, 18),
        side="buy",
    )

    sell_leg = OptionLeg(
        option_type="call",
        strike=Decimal("505"),
        expiration=date(2026, 9, 18),
        side="sell",
    )

    return TradeProposal(
        proposal_id="proposal-024",
        symbol="SPY",
        strategy="defined_risk_option",
        contracts=1,
        legs=(buy_leg, sell_leg),
        net_debit=Decimal("1.00"),
    )


def _evidence(
    evidence_id,
    symbol,
    *,
    source=None,
    as_of=BASE_AS_OF,
    bar_timestamp=None,
):
    if source is None:
        source = (
            "cboe"
            if symbol == "VIX"
            else "alpaca"
        )

    if bar_timestamp is None:
        bar_timestamp = as_of

    bar = MarketBar(
        timestamp=bar_timestamp,
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100"),
        volume=1_000_000,
    )

    return MarketEvidence(
        evidence_id=evidence_id,
        symbol=symbol,
        as_of=as_of,
        source=source,
        bars=(bar,),
    )


def _force_entry_policy_pass(monkeypatch):
    monkeypatch.setattr(
        "lockean_lite.evidence_validation.evaluate_market_entry_policy",
        lambda spy_evidence, vix_evidence: MarketEntryEvaluation(
            passed=True,
            reason="entry_conditions_satisfied",
        ),
    )


def test_evidence_rejects_spy_symbol_that_does_not_match_proposal(monkeypatch):
    _force_entry_policy_pass(monkeypatch)

    result = validate_market_evidence_for_proposal(
        proposal=_proposal(),
        spy_evidence=_evidence("spy-001", "QQQ"),
        vix_evidence=_evidence("vix-001", "VIX"),
    )

    assert result.accepted is False
    assert result.reason == "proposal_evidence_symbol_mismatch"


def test_evidence_rejects_wrong_volatility_symbol(monkeypatch):
    _force_entry_policy_pass(monkeypatch)

    result = validate_market_evidence_for_proposal(
        proposal=_proposal(),
        spy_evidence=_evidence("spy-001", "SPY"),
        vix_evidence=_evidence("vix-001", "SPY"),
    )

    assert result.accepted is False
    assert result.reason == "volatility_evidence_symbol_mismatch"


def test_evidence_rejects_unsupported_source(monkeypatch):
    _force_entry_policy_pass(monkeypatch)

    result = validate_market_evidence_for_proposal(
        proposal=_proposal(),
        spy_evidence=_evidence(
            "spy-001",
            "SPY",
            source="unknown-provider",
        ),
        vix_evidence=_evidence("vix-001", "VIX"),
    )

    assert result.accepted is False
    assert result.reason == "unsupported_evidence_source"


def test_evidence_rejects_mismatched_as_of(monkeypatch):
    _force_entry_policy_pass(monkeypatch)

    result = validate_market_evidence_for_proposal(
        proposal=_proposal(),
        spy_evidence=_evidence("spy-001", "SPY"),
        vix_evidence=_evidence(
            "vix-001",
            "VIX",
            as_of=BASE_AS_OF + timedelta(days=1),
        ),
    )

    assert result.accepted is False
    assert result.reason == "evidence_as_of_mismatch"


def test_evidence_rejects_as_of_that_does_not_match_latest_bar(monkeypatch):
    _force_entry_policy_pass(monkeypatch)

    result = validate_market_evidence_for_proposal(
        proposal=_proposal(),
        spy_evidence=_evidence(
            "spy-001",
            "SPY",
            bar_timestamp=BASE_AS_OF - timedelta(days=1),
        ),
        vix_evidence=_evidence("vix-001", "VIX"),
    )

    assert result.accepted is False
    assert result.reason == "evidence_as_of_inconsistent"


def test_evidence_preserves_market_policy_failure_reason(monkeypatch):
    monkeypatch.setattr(
        "lockean_lite.evidence_validation.evaluate_market_entry_policy",
        lambda spy_evidence, vix_evidence: MarketEntryEvaluation(
            passed=False,
            reason="momentum_filter_failed",
        ),
    )

    result = validate_market_evidence_for_proposal(
        proposal=_proposal(),
        spy_evidence=_evidence("spy-001", "SPY"),
        vix_evidence=_evidence("vix-001", "VIX"),
    )

    assert result.accepted is False
    assert result.reason == "momentum_filter_failed"


def test_validated_evidence_is_bound_to_exact_proposal_fingerprint(monkeypatch):
    _force_entry_policy_pass(monkeypatch)

    proposal = _proposal()

    result = validate_market_evidence_for_proposal(
        proposal=proposal,
        spy_evidence=_evidence("spy-001", "SPY"),
        vix_evidence=_evidence("vix-001", "VIX"),
    )

    assert result.accepted is True
    assert result.reason == "evidence_validated"

    assert result.validated_evidence == ValidatedMarketEvidence(
    proposal_fingerprint=fingerprint_trade_proposal(proposal),
    spy_evidence_id="spy-001",
    vix_evidence_id="vix-001",
    as_of=BASE_AS_OF,
    spy_source="alpaca",
    vix_source="cboe",
)