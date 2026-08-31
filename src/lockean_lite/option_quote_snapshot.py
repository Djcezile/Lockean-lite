from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True)
class OptionQuoteSnapshot:
    contract_symbol: str
    underlying_symbol: str
    option_type: str
    strike: Decimal
    expiration: date
    bid_price: Decimal
    ask_price: Decimal
    quote_timestamp: datetime
    source: str