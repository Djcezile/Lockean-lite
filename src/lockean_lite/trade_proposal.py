from dataclasses import dataclass
from decimal import Decimal

from lockean_lite.option_leg import OptionLeg


@dataclass(frozen=True)
class TradeProposal:
    proposal_id: str
    symbol: str
    strategy: str
    contracts: int
    legs: tuple[OptionLeg, ...] = ()
    net_debit: Decimal | None = None