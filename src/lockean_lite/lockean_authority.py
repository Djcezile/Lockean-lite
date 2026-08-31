from dataclasses import dataclass
from decimal import Decimal

from lockean_lite.evidence_validation import ValidatedMarketEvidence
from lockean_lite.proposal_fingerprint import fingerprint_trade_proposal

from lockean_lite.risk_calculation import (
    calculate_bull_call_spread_maximum_loss,
)
from lockean_lite.trade_proposal import TradeProposal
from lockean_lite.paper_account_snapshot import PaperAccountSnapshot

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from lockean_lite.authorization_receipt import (
    AuthorizationReceipt,
    issue_authorization_receipt,
)


SUPPORTED_STRATEGIES = frozenset(
    {
        "defined_risk_option",
    }
)


@dataclass(frozen=True)
class AuthorityDecision:
    status: str
    reason: str
    proposal_id: str
    authorization_receipt: AuthorizationReceipt | None = None


class LockeanAuthority:
   def __init__(
       self,
       maximum_allowed_loss: Decimal | None = None,
       authorization_signing_key: bytes | None = None,
   ):
       self.maximum_allowed_loss = maximum_allowed_loss
       self.authorization_signing_key = (
           authorization_signing_key
       )

   def evaluate(
        self,
        proposal: TradeProposal,
        account_snapshot: PaperAccountSnapshot | None = None,
        validated_evidence: ValidatedMarketEvidence | None = None,
    ) -> AuthorityDecision:
        if proposal.strategy not in SUPPORTED_STRATEGIES:
            return AuthorityDecision(
                status="REJECTED",
                reason="unsupported_strategy",
                proposal_id=proposal.proposal_id,
            )

        if proposal.contracts <= 0:
            return AuthorityDecision(
                status="REJECTED",
                reason="invalid_contract_quantity",
                proposal_id=proposal.proposal_id,
            )

        if len(proposal.legs) != 2:
            return AuthorityDecision(
                status="REJECTED",
                reason="invalid_leg_count",
                proposal_id=proposal.proposal_id,
            )

        if any(leg.option_type != "call" for leg in proposal.legs):
            return AuthorityDecision(
                status="REJECTED",
                reason="unsupported_option_type",
                proposal_id=proposal.proposal_id,
            )

        sides = {leg.side for leg in proposal.legs}

        if sides != {"buy", "sell"}:
            return AuthorityDecision(
                status="REJECTED",
                reason="invalid_leg_sides",
                proposal_id=proposal.proposal_id,
            )

        expirations = {leg.expiration for leg in proposal.legs}

        if len(expirations) != 1:
            return AuthorityDecision(
                status="REJECTED",
                reason="expiration_mismatch",
                proposal_id=proposal.proposal_id,
            )

        buy_leg = next(
            leg for leg in proposal.legs
            if leg.side == "buy"
        )

        sell_leg = next(
            leg for leg in proposal.legs
            if leg.side == "sell"
        )

        if buy_leg.strike >= sell_leg.strike:
            return AuthorityDecision(
                status="REJECTED",
                reason="invalid_strike_order",
                proposal_id=proposal.proposal_id,
            )

        if proposal.net_debit is None:
            return AuthorityDecision(
            status="REJECTED",
            reason="missing_net_debit",
            proposal_id=proposal.proposal_id,
        )

        if proposal.net_debit <= 0:
            return AuthorityDecision(
            status="REJECTED",
            reason="invalid_net_debit",
            proposal_id=proposal.proposal_id,
        )

        maximum_loss = calculate_bull_call_spread_maximum_loss(
            net_debit=proposal.net_debit,
            contracts=proposal.contracts,
        )

        if (
            self.maximum_allowed_loss is not None
            and maximum_loss > self.maximum_allowed_loss
        ):
            return AuthorityDecision(
                status="REJECTED",
                reason="max_loss_exceeds_limit",
                proposal_id=proposal.proposal_id,
            )

        if (
            account_snapshot is not None
            and account_snapshot.status != "ACTIVE"
        ):
            return AuthorityDecision(
                status="REJECTED",
                reason="account_not_active",
                proposal_id=proposal.proposal_id,
            )

        if (
            account_snapshot is not None
            and account_snapshot.trading_blocked
        ):
            return AuthorityDecision(
                status="REJECTED",
                reason="account_trading_blocked",
                proposal_id=proposal.proposal_id,
            )

        if (
            account_snapshot is not None
            and account_snapshot.options_trading_level < 3
        ):
            return AuthorityDecision(
                status="REJECTED",
                reason="options_level_insufficient",
                proposal_id=proposal.proposal_id,
            )

        if (
            account_snapshot is not None
            and maximum_loss > account_snapshot.options_buying_power
        ):
            return AuthorityDecision(
                status="REJECTED",
                reason="insufficient_options_buying_power",
                proposal_id=proposal.proposal_id,
            )

        if account_snapshot is not None:
            if validated_evidence is None:
                return AuthorityDecision(
                    status="REJECTED",
                    reason="validated_evidence_required",
                    proposal_id=proposal.proposal_id,
                )

            proposal_fingerprint = fingerprint_trade_proposal(
                proposal
            )

            if (
                validated_evidence.proposal_fingerprint
                != proposal_fingerprint
            ):
                return AuthorityDecision(
                    status="REJECTED",
                    reason="validated_evidence_proposal_mismatch",
                    proposal_id=proposal.proposal_id,
                )

        if (
            self.maximum_allowed_loss is None
            or account_snapshot is None
            or validated_evidence is None
            or self.authorization_signing_key is None
        ):
            return AuthorityDecision(
                status="REJECTED",
                reason="authorization_requirements_incomplete",
                proposal_id=proposal.proposal_id,
            )

        proposal_fingerprint = fingerprint_trade_proposal(
            proposal
        )

        issued_at = datetime.now(timezone.utc)
        expires_at = issued_at + timedelta(seconds=30)

        receipt = issue_authorization_receipt(
            receipt_id=str(uuid4()),
            proposal_fingerprint=proposal_fingerprint,
            issued_at=issued_at,
            expires_at=expires_at,
            signing_key=self.authorization_signing_key,
        )

        return AuthorityDecision(
            status="AUTHORIZED",
            reason="authorization_granted",
            proposal_id=proposal.proposal_id,
            authorization_receipt=receipt,
        )



