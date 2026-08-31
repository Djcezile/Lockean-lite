from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PaperAccountSnapshot:
    status: str
    currency: str
    trading_blocked: bool
    options_buying_power: Decimal
    options_approved_level: int
    options_trading_level: int


def create_paper_account_snapshot(account) -> PaperAccountSnapshot:
    return PaperAccountSnapshot(
        status=account.status.value,
        currency=account.currency,
        trading_blocked=account.trading_blocked,
        options_buying_power=Decimal(account.options_buying_power),
        options_approved_level=account.options_approved_level,
        options_trading_level=account.options_trading_level,
    )