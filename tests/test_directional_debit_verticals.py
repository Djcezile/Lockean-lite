from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from alpaca.trading.enums import ContractType

from lockean_lite.ai_recommendation_provider import build_recommendation_prompt
from lockean_lite.alpaca_execution_adapter import resolve_option_contract_symbols
from lockean_lite.evidence_validation import ValidatedMarketEvidence
from lockean_lite.lockean_authority import LockeanAuthority
from lockean_lite.openai_recommendation_model import RECOMMENDATION_SCHEMA
from lockean_lite.option_quote_snapshot import OptionQuoteSnapshot
from lockean_lite.paper_account_snapshot import PaperAccountSnapshot
from lockean_lite.paper_portfolio_snapshot import (
    PaperPortfolioSnapshot,
    PaperPositionSnapshot,
)
from lockean_lite.position_exit_manager import identify_managed_debit_spreads
from lockean_lite.proposal_fingerprint import fingerprint_trade_proposal
from lockean_lite.trade_recommendation import (
    SpreadRecommendation,
    build_trade_proposal_from_recommendation,
)


EXPIRATION = date(2026, 9, 18)
QUOTE_TIME = datetime(2026, 9, 15, 15, 0, tzinfo=timezone.utc)
SIGNING_KEY = b"directional-debit-vertical-test-key"


def _quote(option_type, strike, bid, ask):
    code = "C" if option_type == "call" else "P"
    strike_decimal = Decimal(str(strike))
    return OptionQuoteSnapshot(
        contract_symbol=(
            f"SPY260918{code}"
            f"{int(strike_decimal * 1000):08d}"
        ),
        underlying_symbol="SPY",
        option_type=option_type,
        strike=strike_decimal,
        expiration=EXPIRATION,
        bid_price=Decimal(str(bid)),
        ask_price=Decimal(str(ask)),
        quote_timestamp=QUOTE_TIME,
        source="alpaca",
    )


def _put_candidates():
    return (
        _quote("put", 755, "1.20", "1.25"),
        _quote("put", 760, "2.05", "2.10"),
    )


def _validated_evidence(proposal):
    return ValidatedMarketEvidence(
        proposal_fingerprint=fingerprint_trade_proposal(proposal),
        spy_evidence_id="spy-directional-001",
        vix_evidence_id="vix-directional-001",
        as_of=datetime(2026, 9, 15, 20, 0, tzinfo=timezone.utc),
        spy_source="alpaca",
        vix_source="cboe",
    )


def test_bear_put_recommendation_builds_quote_priced_debit_vertical():
    recommendation = SpreadRecommendation(
        proposal_id="bear-put-001",
        symbol="SPY",
        expiration=EXPIRATION,
        buy_strike=Decimal("760"),
        sell_strike=Decimal("755"),
        contracts=1,
        option_type="put",
    )

    proposal = build_trade_proposal_from_recommendation(
        recommendation=recommendation,
        candidate_quotes=_put_candidates(),
    )

    assert proposal.legs[0].option_type == "put"
    assert proposal.legs[0].side == "buy"
    assert proposal.legs[0].strike == Decimal("760")
    assert proposal.legs[1].option_type == "put"
    assert proposal.legs[1].side == "sell"
    assert proposal.legs[1].strike == Decimal("755")
    assert proposal.net_debit == Decimal("0.90")


def test_bear_put_recommendation_rejects_bull_call_strike_geometry():
    recommendation = SpreadRecommendation(
        proposal_id="bear-put-002",
        symbol="SPY",
        expiration=EXPIRATION,
        buy_strike=Decimal("755"),
        sell_strike=Decimal("760"),
        contracts=1,
        option_type="put",
    )

    with pytest.raises(ValueError, match="invalid_strike_order"):
        build_trade_proposal_from_recommendation(
            recommendation=recommendation,
            candidate_quotes=_put_candidates(),
        )


def test_authority_authorizes_compliant_bear_put_under_same_debit_loss_limit():
    recommendation = SpreadRecommendation(
        proposal_id="bear-put-003",
        symbol="SPY",
        expiration=EXPIRATION,
        buy_strike=Decimal("760"),
        sell_strike=Decimal("755"),
        contracts=1,
        option_type="put",
    )
    proposal = build_trade_proposal_from_recommendation(
        recommendation=recommendation,
        candidate_quotes=_put_candidates(),
    )
    account = PaperAccountSnapshot(
        status="ACTIVE",
        currency="USD",
        trading_blocked=False,
        options_buying_power=Decimal("1000"),
        options_approved_level=3,
        options_trading_level=3,
    )
    authority = LockeanAuthority(
        maximum_allowed_loss=Decimal("150"),
        authorization_signing_key=SIGNING_KEY,
    )

    decision = authority.evaluate(
        proposal,
        account_snapshot=account,
        validated_evidence=_validated_evidence(proposal),
    )

    assert decision.status == "AUTHORIZED"
    assert decision.reason == "authorization_granted"


def test_contract_resolver_requests_exact_put_contracts_for_bear_put():
    recommendation = SpreadRecommendation(
        proposal_id="bear-put-004",
        symbol="SPY",
        expiration=EXPIRATION,
        buy_strike=Decimal("760"),
        sell_strike=Decimal("755"),
        contracts=1,
        option_type="put",
    )
    proposal = build_trade_proposal_from_recommendation(
        recommendation=recommendation,
        candidate_quotes=_put_candidates(),
    )

    class PutClient:
        def __init__(self):
            self.requests = []

        def get_option_contracts(self, request):
            self.requests.append(request)
            strike = Decimal(request.strike_price_gte)
            return SimpleNamespace(
                option_contracts=[
                    SimpleNamespace(
                        symbol=(
                            "SPY260918P00760000"
                            if strike == Decimal("760")
                            else "SPY260918P00755000"
                        ),
                        underlying_symbol="SPY",
                        expiration_date=EXPIRATION,
                        type=ContractType.PUT,
                        strike_price=float(strike),
                        tradable=True,
                    )
                ]
            )

    client = PutClient()
    symbols = resolve_option_contract_symbols(client=client, proposal=proposal)

    assert symbols == (
        "SPY260918P00760000",
        "SPY260918P00755000",
    )
    assert all(request.type == ContractType.PUT for request in client.requests)


def test_exit_reconstruction_recognizes_bear_put_vertical():
    snapshot = PaperPortfolioSnapshot(
        status="ACTIVE",
        currency="USD",
        trading_blocked=False,
        cash=Decimal("99910"),
        equity=Decimal("100000"),
        last_equity=Decimal("100000"),
        buying_power=Decimal("300000"),
        options_buying_power=Decimal("99910"),
        portfolio_value=Decimal("100000"),
        starting_equity=Decimal("100000"),
        total_pl=Decimal("0"),
        day_pl=Decimal("0"),
        unrealized_pl=Decimal("0"),
        positions=(
            PaperPositionSnapshot(
                symbol="SPY260918P00760000",
                asset_class="us_option",
                qty=Decimal("1"),
                market_value=Decimal("100"),
                cost_basis=Decimal("210"),
                current_price=Decimal("1.00"),
                unrealized_pl=Decimal("-110"),
                unrealized_plpc=Decimal("-0.52"),
            ),
            PaperPositionSnapshot(
                symbol="SPY260918P00755000",
                asset_class="us_option",
                qty=Decimal("-1"),
                market_value=Decimal("-40"),
                cost_basis=Decimal("-120"),
                current_price=Decimal("0.40"),
                unrealized_pl=Decimal("80"),
                unrealized_plpc=Decimal("0.66"),
            ),
        ),
        option_contract_units=Decimal("2"),
        managed_spreads=1,
    )

    spreads = identify_managed_debit_spreads(snapshot)

    assert len(spreads) == 1
    spread = spreads[0]
    assert spread.option_type == "put"
    assert spread.long_strike == Decimal("760")
    assert spread.short_strike == Decimal("755")
    assert spread.entry_debit_per_contract == Decimal("0.90")


def test_directional_prompt_and_schema_allow_call_or_put_without_forcing_trade():
    prompt = build_recommendation_prompt(
        proposal_id="directional-prompt-001",
        candidate_quotes=(
            _quote("call", 760, "1.00", "1.05"),
            *_put_candidates(),
        ),
        activity_mode="balanced",
    )

    assert "option_type" in prompt
    assert "bull call" in prompt
    assert "bear put" in prompt
    assert "Prefer decision=TRADE" not in prompt
    assert "option_type=call" in prompt
    assert "option_type=put" in prompt

    option_type_schema = RECOMMENDATION_SCHEMA["properties"]["option_type"]
    assert "call" in option_type_schema["enum"]
    assert "put" in option_type_schema["enum"]
    assert "option_type" in RECOMMENDATION_SCHEMA["required"]
