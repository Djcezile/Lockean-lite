from decimal import Decimal


OPTION_CONTRACT_MULTIPLIER = Decimal("100")


def calculate_bull_call_spread_maximum_loss(
    net_debit: Decimal,
    contracts: int,
) -> Decimal:
    return (
        net_debit
        * OPTION_CONTRACT_MULTIPLIER
        * Decimal(contracts)
    )