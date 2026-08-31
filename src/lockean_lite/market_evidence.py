from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class MarketBar:
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


@dataclass(frozen=True)
class MarketEvidence:
    evidence_id: str
    symbol: str
    as_of: datetime
    source: str
    bars: tuple[MarketBar, ...]