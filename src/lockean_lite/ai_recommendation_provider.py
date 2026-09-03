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


def build_recommendation_prompt(
    *,
    proposal_id: str,
    candidate_quotes: tuple[
        OptionQuoteSnapshot,
        ...,
    ],
    maximum_allowed_loss: Decimal | None = None,
    market_context: dict[str, str] | None = None,
) -> str:
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

    if maximum_allowed_loss is not None:
        policy_context = (
        "\nLOCKEAN POLICY CONTEXT:\n"
        f"maximum_allowed_loss_usd="
        f"{maximum_allowed_loss}\n"
        "Use this only to improve your recommendation. "
        "Lockean independently determines pricing, risk, "
        "compliance, and authorization.\n"
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
    "authorization decisions, or broker instructions.\n"
    f"{policy_context}\n"
    f"{market_context_text}\n"
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
):
        self.maximum_allowed_loss = (
            maximum_allowed_loss
        )
        self.proposal_id_provider = (
            proposal_id_provider
        )

        self.model_callable = model_callable

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