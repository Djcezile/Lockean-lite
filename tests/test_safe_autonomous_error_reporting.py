from decimal import Decimal
from types import SimpleNamespace

from lockean_lite.autonomous_session import (
    run_autonomous_paper_session,
)
from lockean_lite.paper_portfolio_snapshot import (
    PaperPortfolioSnapshot,
)


def _portfolio():
    return PaperPortfolioSnapshot(
        status="ACTIVE",
        currency="USD",
        trading_blocked=False,
        cash=Decimal("100000"),
        equity=Decimal("100000"),
        last_equity=Decimal("100000"),
        buying_power=Decimal("200000"),
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


def _open_clock():
    return SimpleNamespace(
        is_open=True,
        next_open="next-open",
        next_close="next-close",
    )


def test_session_logs_machine_safe_value_error_reason():
    output = []

    def failing_cycle():
        raise ValueError("ai_model_request_failed")

    summary = run_autonomous_paper_session(
        clock_provider=_open_clock,
        portfolio_provider=_portfolio,
        cycle_runner=failing_cycle,
        interval_seconds=1,
        sleep_fn=lambda seconds: None,
        output_fn=output.append,
        max_iterations=1,
    )

    assert summary.last_status == "CYCLE_ERROR"
    assert summary.last_reason == "ai_model_request_failed"
    assert any(
        line
        == "AUTONOMOUS CYCLE: ERROR | ValueError | ai_model_request_failed"
        for line in output
    )


def test_session_redacts_free_form_value_error_text():
    output = []

    def failing_cycle():
        raise ValueError(
            "provider rejected payload containing secret material"
        )

    summary = run_autonomous_paper_session(
        clock_provider=_open_clock,
        portfolio_provider=_portfolio,
        cycle_runner=failing_cycle,
        interval_seconds=1,
        sleep_fn=lambda seconds: None,
        output_fn=output.append,
        max_iterations=1,
    )

    joined = "\n".join(output)

    assert summary.last_reason == "value_error"
    assert "secret material" not in joined
    assert (
        "AUTONOMOUS CYCLE: ERROR | ValueError | value_error"
        in joined
    )
