from decimal import Decimal

from lockean_lite.risk_calculation import (
    calculate_bull_call_spread_maximum_loss,
)


def test_bull_call_spread_maximum_loss_is_derived_from_net_debit_and_contracts():
    maximum_loss = calculate_bull_call_spread_maximum_loss(
        net_debit=Decimal("1.25"),
        contracts=2,
    )

    assert maximum_loss == Decimal("250.00")