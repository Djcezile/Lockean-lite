from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from alpaca.trading.enums import ContractType

from lockean_lite.alpaca_option_quote_adapter import (
    read_spy_call_candidate_quotes,
    translate_alpaca_option_quote,
)
from lockean_lite.option_quote_snapshot import (
    OptionQuoteSnapshot,
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


def _contract(
    *,
    symbol,
    strike,
    tradable=True,
):
    return SimpleNamespace(
        symbol=symbol,
        underlying_symbol="SPY",
        expiration_date=date(2026, 9, 18),
        type=ContractType.CALL,
        strike_price=float(strike),
        tradable=tradable,
    )


def _quote(
    *,
    bid,
    ask,
):
    return SimpleNamespace(
        bid_price=float(bid),
        ask_price=float(ask),
        timestamp=QUOTE_TIME,
    )


def test_alpaca_option_quote_translates_to_immutable_lockean_snapshot():
    contract = _contract(
        symbol="SPY260918C00782000",
        strike=Decimal("782"),
    )

    quote = _quote(
        bid=Decimal("2.96"),
        ask=Decimal("3.03"),
    )

    result = translate_alpaca_option_quote(
        contract=contract,
        quote=quote,
    )

    assert result == OptionQuoteSnapshot(
        contract_symbol="SPY260918C00782000",
        underlying_symbol="SPY",
        option_type="call",
        strike=Decimal("782"),
        expiration=date(2026, 9, 18),
        bid_price=Decimal("2.96"),
        ask_price=Decimal("3.03"),
        quote_timestamp=QUOTE_TIME,
        source="alpaca",
    )


def test_option_quote_translation_rejects_non_tradable_contract():
    contract = _contract(
        symbol="SPY260918C00782000",
        strike=Decimal("782"),
        tradable=False,
    )

    with pytest.raises(
        ValueError,
        match="option_contract_not_tradable",
    ):
        translate_alpaca_option_quote(
            contract=contract,
            quote=_quote(
                bid=Decimal("2.96"),
                ask=Decimal("3.03"),
            ),
        )


def test_option_quote_translation_rejects_invalid_market():
    contract = _contract(
        symbol="SPY260918C00782000",
        strike=Decimal("782"),
    )

    with pytest.raises(
        ValueError,
        match="invalid_option_quote",
    ):
        translate_alpaca_option_quote(
            contract=contract,
            quote=_quote(
                bid=Decimal("3.50"),
                ask=Decimal("3.00"),
            ),
        )


class FakeTradingClient:
    def get_option_contracts(self, request):
        return SimpleNamespace(
            option_contracts=[
                _contract(
                    symbol="SPY260918C00787000",
                    strike=Decimal("787"),
                ),
                _contract(
                    symbol="SPY260918C00782000",
                    strike=Decimal("782"),
                ),
            ]
        )


class FakeOptionDataClient:
    def get_option_latest_quote(self, request):
        return {
            "SPY260918C00782000": _quote(
                bid=Decimal("2.96"),
                ask=Decimal("3.03"),
            ),
            "SPY260918C00787000": _quote(
                bid=Decimal("1.75"),
                ask=Decimal("1.76"),
            ),
        }


def test_candidate_reader_returns_deterministic_strike_sorted_snapshots():
    results = read_spy_call_candidate_quotes(
        trading_client=FakeTradingClient(),
        option_data_client=FakeOptionDataClient(),
        expiration=date(2026, 9, 18),
        minimum_strike=Decimal("780"),
        maximum_strike=Decimal("790"),
    )

    assert tuple(
        quote.strike
        for quote in results
    ) == (
        Decimal("782"),
        Decimal("787"),
    )

    assert results[0].contract_symbol == (
        "SPY260918C00782000"
    )

    assert results[1].contract_symbol == (
        "SPY260918C00787000"
    )


def test_candidate_reader_fails_closed_when_no_usable_quotes_exist():
    class EmptyTradingClient:
        def get_option_contracts(self, request):
            return SimpleNamespace(
                option_contracts=[]
            )

    with pytest.raises(
        ValueError,
        match="option_candidate_universe_empty",
    ):
        read_spy_call_candidate_quotes(
            trading_client=EmptyTradingClient(),
            option_data_client=FakeOptionDataClient(),
            expiration=date(2026, 9, 18),
            minimum_strike=Decimal("780"),
            maximum_strike=Decimal("790"),
        )