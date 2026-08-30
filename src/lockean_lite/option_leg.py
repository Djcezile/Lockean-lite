from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class OptionLeg:
    option_type: str
    strike: Decimal
    expiration: date
    side: str