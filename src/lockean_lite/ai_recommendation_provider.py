import json

from datetime import date
from decimal import Decimal

from lockean_lite.option_quote_snapshot import (
    OptionQuoteSnapshot,
)
from lockean_lite.trade_recommendation import (
    SpreadRecommendation,
)


REQUIRED_RESPONSE_FIELDS = frozenset(
    {
        "symbol",
        "expiration",
        "buy_strike",
        "sell_strike",
        "contracts",
    }
)

NO_TRADE_RESPONSE_FIELDS = frozenset(
    {
        "decision",
        "symbol",
        "expiration",
        "buy_strike",
        "sell_strike",
        "contracts",
    }
)

SUPPORTED_ACTIVITY_MODES = frozenset(
    {
        "balanced",
        "active_paper",
    }
)


def build_recommendation_prompt(
    *,
    proposal_id: str,
    candidate_quotes: tuple[
        OptionQuoteSnapshot,
        ...,
    ],
    maximum_allowed_loss: Decimal | None = None,
    market_context: dict[str, str] | None = None,
    activity_mode: str = "balanced",
) -> str:
    if activity_mode not in SUPPORTED_ACTIVITY_MODES:
        raise ValueError(
            "unsupported_agent_activity_mode"
        )

    candidate_lines = []

    for quote in candidate_quotes:
        candidate_lines.append(
            (
                f"strike={quote.strike}, "
                f"bid={quote.bid_price}, "
                f"ask={quote.ask_price}, "
                f"expiration={quote.expiration.isoformat()}"
            )
        )

    candidate_text = "\n".join(
        candidate_lines
    )

    policy_context = ""

    if maximum_allowed_loss is not None:
        policy_context = (
            "\nLOCKEAN POLICY CONTEXT:\n"
            "maximum_allowed_loss_usd="
            f"{maximum_allowed_loss}\n"
            "Use this only to improve your recommendation. "
            "Lockean independently determines pricing, risk, "
            "compliance, and permission.\n"
        )

    market_context_text = ""

    if market_context is not None:
        market_context_lines = [
            f"{key}={value}"
            for key, value in market_context.items()
        ]

        market_context_text = (
            "\nMARKET CONTEXT:\n"
            + "\n".join(market_context_lines)
            + "\n"
        )

    activity_context = ""

    if activity_mode == "active_paper":
        activity_context = (
            "\nACTIVE PAPER MODE:\n"
            "This is an Alpaca PAPER account. The goal is to "
            "exercise the complete autonomous trading loop and "
            "collect realistic paper performance data while all "
            "Lockean limits remain unchanged.\n"
            "Prefer decision=TRADE when at least one candidate "
            "pair forms a sensible defined-risk bull call spread, "
            "its quoted debit appears likely to fit the supplied "
            "maximum-loss context, and the market context is not "
            "strongly adverse.\n"
            "Treat individual PASS/FAIL market signals as context, "
            "not independent hard vetoes. A single FAIL does not "
            "by itself require NO_TRADE.\n"
            "Favor reasonably tight, liquid-looking candidate "
            "spreads and narrower strike widths when several "
            "choices are comparable.\n"
            "Use decision=NO_TRADE when the candidates are clearly "
            "poor, structurally unsuitable, or the combined market "
            "evidence is materially adverse.\n"
            "You still have no permission or broker authority. "
            "Lockean independently reconstructs pricing and risk "
            "and may reject any proposal.\n"
        )

    return (
        "You are the trading agent.\n\n"
        "You decide whether the market opportunity "
        "justifies a trade.\n\n"
        "If you want to propose a defined-risk SPY bull "
        "call spread using the candidate options below, "
        "set decision=TRADE.\n"
        "If you do not want to trade, "
        "set decision=NO_TRADE.\n\n"
        "Return JSON only with exactly these fields:\n"
        "decision\n"
        "symbol\n"
        "expiration\n"
        "buy_strike\n"
        "sell_strike\n"
        "contracts\n\n"
        "For decision=NO_TRADE, symbol, expiration, "
        "buy_strike, sell_strike, and contracts "
        "must all be null.\n"
        "For decision=TRADE, populate those fields using "
        "only the candidate options below.\n\n"
        "Do not return pricing, risk calculations, "
        "permission decisions, or broker instructions.\n"
        f"{policy_context}"
        f"{market_context_text}"
        f"{activity_context}\n"
        f"proposal_reference={proposal_id}\n\n"
        "CANDIDATES:\n"
        f"{candidate_text}"
    )


class StructuredAIRecommendationProvider:
    def __init__(
        self,
        *,
        proposal_id_provider,
        model_callable,
        maximum_allowed_loss: Decimal | None = None,
        activity_mode: str = "balanced",
    ):
        if activity_mode not in SUPPORTED_ACTIVITY_MODES:
            raise ValueError(
                "unsupported_agent_activity_mode"
            )

        self.maximum_allowed_loss = (
            maximum_allowed_loss
        )
        self.proposal_id_provider = (
            proposal_id_provider
        )
        self.model_callable = model_callable
        self.activity_mode = activity_mode

    def __call__(
        self,
        candidate_quotes: tuple[
            OptionQuoteSnapshot,
            ...,
        ],
        market_context: dict[str, str] | None = None,
    ) -> SpreadRecommendation | None:
        proposal_id = (
            self.proposal_id_provider()
        )

        prompt = build_recommendation_prompt(
            proposal_id=proposal_id,
            candidate_quotes=candidate_quotes,
            maximum_allowed_loss=(
                self.maximum_allowed_loss
            ),
            market_context=market_context,
            activity_mode=self.activity_mode,
        )

        raw_response = self.model_callable(
            prompt
        )

        try:
            parsed = json.loads(
                raw_response
            )
        except (
            json.JSONDecodeError,
            TypeError,
        ) as error:
            raise ValueError(
                "ai_recommendation_invalid_json"
            ) from error

        if (
            isinstance(parsed, dict)
            and frozenset(parsed.keys())
            == NO_TRADE_RESPONSE_FIELDS
        ):
            decision = parsed["decision"]

            if decision == "NO_TRADE":
                no_trade_fields = (
                    "symbol",
                    "expiration",
                    "buy_strike",
                    "sell_strike",
                    "contracts",
                )

                if not all(
                    parsed[field] is None
                    for field in no_trade_fields
                ):
                    raise ValueError(
                        "ai_recommendation_schema_invalid"
                    )

                return None

            if decision == "TRADE":
                parsed = {
                    field: parsed[field]
                    for field in REQUIRED_RESPONSE_FIELDS
                }

            else:
                raise ValueError(
                    "ai_recommendation_schema_invalid"
                )

        if (
            not isinstance(parsed, dict)
            or frozenset(parsed.keys())
            != REQUIRED_RESPONSE_FIELDS
        ):
            raise ValueError(
                "ai_recommendation_schema_invalid"
            )

        try:
            symbol = str(
                parsed["symbol"]
            )

            expiration = date.fromisoformat(
                str(
                    parsed["expiration"]
                )
            )

            buy_strike = Decimal(
                str(
                    parsed["buy_strike"]
                )
            )

            sell_strike = Decimal(
                str(
                    parsed["sell_strike"]
                )
            )

            contracts = int(
                parsed["contracts"]
            )

        except (
            ValueError,
            TypeError,
            ArithmeticError,
        ) as error:
            raise ValueError(
                "ai_recommendation_schema_invalid"
            ) from error

        return SpreadRecommendation(
            proposal_id=proposal_id,
            symbol=symbol,
            expiration=expiration,
            buy_strike=buy_strike,
            sell_strike=sell_strike,
            contracts=contracts,
        )
