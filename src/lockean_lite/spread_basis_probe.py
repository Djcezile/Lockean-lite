from lockean_lite.alpaca_client_factory import (
    create_paper_trading_client_from_environment,
)
from lockean_lite.filled_spread_basis import (
    recover_open_spread_entry_basis,
    render_spread_basis_recovery_report,
)
from lockean_lite.paper_portfolio_snapshot import (
    read_live_paper_portfolio_snapshot,
)
from lockean_lite.position_exit_manager import (
    identify_managed_debit_spreads,
)


def _current_open_option_symbols(snapshot) -> tuple[str, ...]:
    return tuple(
        sorted(
            position.symbol
            for position in snapshot.positions
            if position.qty != 0
            and "option" in position.asset_class.lower()
        )
    )


def build_live_probe_report(
    *,
    recovery_result,
    snapshot,
) -> str:
    spreads = identify_managed_debit_spreads(
        snapshot,
        entry_basis_by_structure=(
            recovery_result.basis_by_structure
        ),
    )
    recovered_units = sum(
        spread.contracts
        for spread in spreads
    )
    expected_units = int(snapshot.managed_spreads)
    open_symbols = _current_open_option_symbols(snapshot)

    lines = [
        render_spread_basis_recovery_report(
            recovery_result
        ),
        "",
        "LIVE PORTFOLIO CROSS-CHECK",
        "==========================",
        f"current_managed_spread_units={expected_units}",
        f"recovered_managed_spread_units={recovered_units}",
        (
            "recovery_matches_open_portfolio="
            f"{recovered_units == expected_units}"
        ),
        (
            "current_open_option_symbols="
            + ",".join(open_symbols)
        ),
    ]

    if recovered_units < expected_units:
        lines.append(
            "RESULT: FAIL_CLOSED_BASIS_GAP"
        )
    else:
        lines.append(
            "RESULT: BASIS_RECOVERY_COVERS_OPEN_PORTFOLIO"
        )

    return "\n".join(lines)


def main() -> int:
    trading_client = (
        create_paper_trading_client_from_environment()
    )

    recovery_result = recover_open_spread_entry_basis(
        trading_client=trading_client
    )
    snapshot = read_live_paper_portfolio_snapshot(
        trading_client=trading_client
    )

    print(
        build_live_probe_report(
            recovery_result=recovery_result,
            snapshot=snapshot,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
