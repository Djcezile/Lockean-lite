import hashlib
import json
from decimal import Decimal

from lockean_lite.trade_proposal import TradeProposal


FINGERPRINT_VERSION = 1


def _canonical_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")


def fingerprint_trade_proposal(proposal: TradeProposal) -> str:
    canonical_legs = sorted(
        (
            {
                "option_type": leg.option_type,
                "strike": _canonical_decimal(leg.strike),
                "expiration": leg.expiration.isoformat(),
                "side": leg.side,
            }
            for leg in proposal.legs
        ),
        key=lambda leg: (
            leg["side"],
            leg["option_type"],
            leg["strike"],
            leg["expiration"],
        ),
    )

    payload = {
        "fingerprint_version": FINGERPRINT_VERSION,
        "proposal_id": proposal.proposal_id,
        "symbol": proposal.symbol,
        "strategy": proposal.strategy,
        "contracts": proposal.contracts,
        "net_debit": (
            _canonical_decimal(proposal.net_debit)
            if proposal.net_debit is not None
            else None
        ),
        "legs": canonical_legs,
    }

    canonical_json = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        canonical_json.encode("utf-8")
    ).hexdigest()