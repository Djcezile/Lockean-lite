from decimal import Decimal
from types import SimpleNamespace

from lockean_lite.autonomous_session import run_autonomous_paper_session
from lockean_lite.paper_portfolio_snapshot import PaperPortfolioSnapshot


def _portfolio():
    return PaperPortfolioSnapshot(
        status="ACTIVE",
        currency="USD",
        trading_blocked=False,
        cash=Decimal("100000"),
        equity=Decimal("100000"),
        last_equity=Decimal("100000"),
        buying_power=Decimal("400000"),
        options_buying_power=Decimal("100000"),
        portfolio_value=Decimal("100000"),
        starting_equity=Decimal("100000"),
        total_pl=Decimal("0"),
        day_pl=Decimal("0"),
        unrealized_pl=Decimal("0"),
        positions=(),
        option_contract_units=Decimal("0"),
        managed_spreads=0,
    )


def test_submitted_exit_logs_observed_and_submitted_credit():
    output = []
    exit_result = SimpleNamespace(
        submitted=True,
        reason="take_profit_exit_submitted",
        broker_order_id="exit-1",
        expected_return_percent=Decimal("36.00"),
        block_new_entries=False,
        cancelled_order_ids=(),
        observed_close_credit=Decimal("0.68"),
        submitted_limit_credit=Decimal("0.66"),
        submitted_limit_return_percent=Decimal("32.00"),
        entry_debit_per_contract=Decimal("0.50"),
        contracts=1,
        long_symbol="SPY260918C00762000",
        short_symbol="SPY260918C00764000",
    )

    run_autonomous_paper_session(
        clock_provider=lambda: SimpleNamespace(
            is_open=True,
            next_open="next-open",
            next_close="next-close",
        ),
        portfolio_provider=_portfolio,
        cycle_runner=lambda: None,
        exit_runner=lambda snapshot: exit_result,
        interval_seconds=1,
        sleep_fn=lambda seconds: None,
        output_fn=output.append,
        max_iterations=1,
    )

    pricing_lines = [
        line for line in output
        if line.startswith("POSITION EXIT PRICING:")
    ]
    assert len(pricing_lines) == 1
    line = pricing_lines[0]
    assert "entry_debit=0.50" in line
    assert "observed_credit=0.68" in line
    assert "submitted_limit_credit=0.66" in line
    assert "limit_return=32.00%" in line
    assert "contracts=1" in line
