from dataclasses import dataclass


@dataclass(frozen=True)
class TradeProposal:
    proposal_id: str
    symbol: str
    strategy: str
    contracts: int