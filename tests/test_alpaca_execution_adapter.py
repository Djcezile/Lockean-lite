from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from alpaca.trading.enums import (
    ContractType,
    OrderClass,
    OrderSide,
    PositionIntent,
    TimeInForce,
)

from lockean_lite.alpaca_execution_adapter import (
    build_authorized_mleg_limit_order,
    resolve_option_contract_symbols,
)
from lockean_lite.option_leg import OptionLeg
from lockean_lite.trade_proposal import TradeProposal


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
        proposal_id="proposal-030",
        symbol="SPY",
        strategy="defined_risk_option",
        contracts=1,
        legs=(buy_leg, sell_leg),
        net_debit=Decimal("1.25"),
    )


class FakeTradingClient:
    def __init__(self):
        self.requests = []

    def get_option_contracts(self, request):
        self.requests.append(request)

        strike = Decimal(request.strike_price_gte)

        symbol = (
            "SPY260918C00500000"
            if strike == Decimal("500")
            else "SPY260918C00505000"
        )

        contract = SimpleNamespace(
            symbol=symbol,
            underlying_symbol="SPY",
            expiration_date=date(2026, 9, 18),
            type=ContractType.CALL,
            strike_price=float(strike),
            tradable=True,
        )

        return SimpleNamespace(
            option_contracts=[contract],
        )


def test_resolver_derives_exact_contract_symbols_from_proposal_terms():
    proposal = _proposal()
    client = FakeTradingClient()

    resolved = resolve_option_contract_symbols(
        client=client,
        proposal=proposal,
    )

    assert resolved == (
        "SPY260918C00500000",
        "SPY260918C00505000",
    )

    assert len(client.requests) == 2


def test_resolver_fails_closed_when_exact_contract_is_missing():
    proposal = _proposal()

    class MissingContractClient:
        def get_option_contracts(self, request):
            return SimpleNamespace(
                option_contracts=[],
            )

    with pytest.raises(
        ValueError,
        match="option_contract_not_found",
    ):
        resolve_option_contract_symbols(
            client=MissingContractClient(),
            proposal=proposal,
        )


def test_resolver_fails_closed_when_contract_resolution_is_ambiguous():
    proposal = _proposal()

    class AmbiguousContractClient:
        def get_option_contracts(self, request):
            strike = Decimal(request.strike_price_gte)

            contract = SimpleNamespace(
                symbol="duplicate",
                underlying_symbol="SPY",
                expiration_date=date(2026, 9, 18),
                type=ContractType.CALL,
                strike_price=float(strike),
                tradable=True,
            )

            return SimpleNamespace(
                option_contracts=[
                    contract,
                    contract,
                ],
            )

    with pytest.raises(
        ValueError,
        match="option_contract_ambiguous",
    ):
        resolve_option_contract_symbols(
            client=AmbiguousContractClient(),
            proposal=proposal,
        )


def test_authorized_bull_call_becomes_exact_mleg_debit_limit_order():
    proposal = _proposal()

    order = build_authorized_mleg_limit_order(
        proposal=proposal,
        contract_symbols=(
            "SPY260918C00500000",
            "SPY260918C00505000",
        ),
    )

    assert order.order_class == OrderClass.MLEG
    assert order.qty == 1
    assert order.time_in_force == TimeInForce.DAY
    assert order.limit_price == 1.25

    assert len(order.legs) == 2

    buy_leg = order.legs[0]
    sell_leg = order.legs[1]

    assert buy_leg.symbol == "SPY260918C00500000"
    assert buy_leg.ratio_qty == 1
    assert buy_leg.side == OrderSide.BUY
    assert buy_leg.position_intent == PositionIntent.BUY_TO_OPEN

    assert sell_leg.symbol == "SPY260918C00505000"
    assert sell_leg.ratio_qty == 1
    assert sell_leg.side == OrderSide.SELL
    assert sell_leg.position_intent == PositionIntent.SELL_TO_OPEN