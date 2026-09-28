from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from lockean_lite.option_leg import OptionLeg
from lockean_lite.session_loss_loop_policy import (
    SessionLossLoopState,
    evaluate_session_loss_loop_proposal,
    read_session_loss_loop_state,
)
from lockean_lite.trade_proposal import TradeProposal


NOW = datetime(2026, 9, 29, 15, 0, tzinfo=timezone.utc)


class FakeTradingClient:
    def __init__(self, orders):
        self.orders = orders
        self.filters = []

    def get_orders(self, *, filter):
        self.filters.append(filter)
        return self.orders


def _order(
    *,
    order_id,
    client_order_id,
    filled_qty,
    filled_at,
):
    return SimpleNamespace(
        id=order_id,
        client_order_id=client_order_id,
        filled_qty=filled_qty,
        filled_at=filled_at,
    )


def _proposal(option_type):
    return TradeProposal(
        proposal_id="proposal-001",
        symbol="SPY",
        strategy="defined_risk_option",
        contracts=1,
        legs=(
            OptionLeg(
                option_type=option_type,
                strike=770,
                expiration=NOW.date(),
                side="buy",
            ),
            OptionLeg(
                option_type=option_type,
                strike=771,
                expiration=NOW.date(),
                side="sell",
            ),
        ),
    )


def test_one_confirmed_stop_fill_blocks_only_that_direction_for_one_hour():
    fill_time = NOW - timedelta(minutes=15)
    client = FakeTradingClient(
        [
            _order(
                order_id="cancelled-retry-1",
                client_order_id="lockean-sl-call-cancelled-1",
                filled_qty="0",
                filled_at=None,
            ),
            _order(
                order_id="cancelled-retry-2",
                client_order_id="lockean-sl-call-cancelled-2",
                filled_qty="0",
                filled_at=None,
            ),
            _order(
                order_id="cancelled-retry-3",
                client_order_id="lockean-sl-call-cancelled-3",
                filled_qty="0",
                filled_at=None,
            ),
            _order(
                order_id="filled-stop",
                client_order_id="lockean-sl-call-filled",
                filled_qty="1",
                filled_at=fill_time,
            ),
        ]
    )

    state = read_session_loss_loop_state(
        trading_client=client,
        now=NOW,
        direction_cooldown_seconds=3600,
        maximum_stop_loss_fills=2,
    )

    assert state.confirmed_stop_loss_fills == 1
    assert state.blocked_direction == "bullish"
    assert state.cooldown_until == fill_time + timedelta(hours=1)
    assert not state.halt_all_entries
    assert state.reason == "same_direction_stop_loss_cooldown"
    assert client.filters[0].nested is True

    assert not evaluate_session_loss_loop_proposal(
        proposal=_proposal("call"),
        state=state,
    ).allowed
    assert evaluate_session_loss_loop_proposal(
        proposal=_proposal("put"),
        state=state,
    ).allowed


def test_direction_cooldown_expires_without_erasing_confirmed_fill_count():
    fill_time = NOW - timedelta(hours=1)
    state = read_session_loss_loop_state(
        trading_client=FakeTradingClient(
            [
                _order(
                    order_id="filled-stop",
                    client_order_id="lockean-sl-put-filled",
                    filled_qty="1",
                    filled_at=fill_time,
                )
            ]
        ),
        now=NOW,
        direction_cooldown_seconds=3600,
        maximum_stop_loss_fills=2,
    )

    assert state.confirmed_stop_loss_fills == 1
    assert state.blocked_direction is None
    assert state.cooldown_until is None
    assert state.reason == "loss_loop_entry_allowed"


def test_second_confirmed_stop_fill_halts_all_entries_for_session():
    state = read_session_loss_loop_state(
        trading_client=FakeTradingClient(
            [
                _order(
                    order_id="first-stop",
                    client_order_id="lockean-sl-call-first",
                    filled_qty="1",
                    filled_at=NOW - timedelta(hours=2),
                ),
                _order(
                    order_id="second-stop",
                    client_order_id="lockean-sl-put-second",
                    filled_qty="1",
                    filled_at=NOW - timedelta(minutes=1),
                ),
            ]
        ),
        now=NOW,
        direction_cooldown_seconds=3600,
        maximum_stop_loss_fills=2,
    )

    assert state.confirmed_stop_loss_fills == 2
    assert state.halt_all_entries
    assert state.blocked_direction is None
    assert state.reason == "session_stop_loss_limit_reached"
    assert not evaluate_session_loss_loop_proposal(
        proposal=_proposal("put"),
        state=state,
    ).allowed


def test_multi_unit_stop_fill_counts_each_closed_spread_unit():
    state = read_session_loss_loop_state(
        trading_client=FakeTradingClient(
            [
                _order(
                    order_id="two-unit-stop",
                    client_order_id="lockean-sl-call-two-units",
                    filled_qty="2",
                    filled_at=NOW - timedelta(minutes=1),
                )
            ]
        ),
        now=NOW,
        maximum_stop_loss_fills=2,
    )

    assert state.confirmed_stop_loss_fills == 2
    assert state.halt_all_entries


def test_duplicate_broker_order_rows_do_not_double_count_fill():
    order = _order(
        order_id="one-stop",
        client_order_id="lockean-sl-call-one",
        filled_qty="1",
        filled_at=NOW - timedelta(minutes=1),
    )

    state = read_session_loss_loop_state(
        trading_client=FakeTradingClient([order, order]),
        now=NOW,
        maximum_stop_loss_fills=2,
    )

    assert state.confirmed_stop_loss_fills == 1
    assert not state.halt_all_entries


def test_state_is_reconstructed_from_broker_history_after_restart():
    client = FakeTradingClient(
        [
            _order(
                order_id="durable-stop",
                client_order_id="lockean-sl-put-durable",
                filled_qty="1",
                filled_at=NOW - timedelta(minutes=10),
            )
        ]
    )

    first_process_state = read_session_loss_loop_state(
        trading_client=client,
        now=NOW,
    )
    restarted_process_state = read_session_loss_loop_state(
        trading_client=client,
        now=NOW,
    )

    assert restarted_process_state == first_process_state
    assert restarted_process_state.blocked_direction == "bearish"


def test_prior_market_day_stop_fill_does_not_carry_into_new_session():
    state = read_session_loss_loop_state(
        trading_client=FakeTradingClient(
            [
                _order(
                    order_id="prior-day-stop",
                    client_order_id="lockean-sl-call-prior",
                    filled_qty="1",
                    filled_at=NOW - timedelta(days=1),
                )
            ]
        ),
        now=NOW,
    )

    assert state.confirmed_stop_loss_fills == 0
    assert state.reason == "loss_loop_entry_allowed"


def test_take_profit_fill_does_not_count_as_stop_loss():
    state = read_session_loss_loop_state(
        trading_client=FakeTradingClient(
            [
                _order(
                    order_id="profit-fill",
                    client_order_id="lockean-tp-call-profit",
                    filled_qty="1",
                    filled_at=NOW - timedelta(minutes=1),
                )
            ]
        ),
        now=NOW,
    )

    assert state.confirmed_stop_loss_fills == 0
    assert not state.halt_all_entries


def test_tagged_fill_without_time_fails_closed():
    with pytest.raises(ValueError, match="stop_loss_fill_time_missing"):
        read_session_loss_loop_state(
            trading_client=FakeTradingClient(
                [
                    _order(
                        order_id="ambiguous-stop",
                        client_order_id="lockean-sl-call-ambiguous",
                        filled_qty="1",
                        filled_at=None,
                    )
                ]
            ),
            now=NOW,
        )


def test_invalid_policy_thresholds_are_rejected():
    client = FakeTradingClient([])

    with pytest.raises(
        ValueError,
        match="direction_cooldown_seconds_must_be_non_negative",
    ):
        read_session_loss_loop_state(
            trading_client=client,
            now=NOW,
            direction_cooldown_seconds=-1,
        )

    with pytest.raises(
        ValueError,
        match="maximum_stop_loss_fills_must_be_positive",
    ):
        read_session_loss_loop_state(
            trading_client=client,
            now=NOW,
            maximum_stop_loss_fills=0,
        )


def test_proposal_evaluation_fails_closed_for_ambiguous_direction():
    ambiguous = TradeProposal(
        proposal_id="ambiguous",
        symbol="SPY",
        strategy="defined_risk_option",
        contracts=1,
        legs=(),
    )
    state = SessionLossLoopState(
        confirmed_stop_loss_fills=1,
        blocked_direction="bullish",
        cooldown_until=NOW + timedelta(minutes=30),
        halt_all_entries=False,
        reason="same_direction_stop_loss_cooldown",
    )

    decision = evaluate_session_loss_loop_proposal(
        proposal=ambiguous,
        state=state,
    )

    assert not decision.allowed
    assert decision.reason == "loss_loop_proposal_direction_ambiguous"
