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

DIRECTIONAL_REQUIRED_RESPONSE_FIELDS = frozenset(
    set(REQUIRED_RESPONSE_FIELDS)
    | {"option_type"}
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

DIRECTIONAL_NO_TRADE_RESPONSE_FIELDS = frozenset(
    set(NO_TRADE_RESPONSE_FIELDS)
    | {"option_type"}
)

SUPPORTED_ACTIVITY_MODES = frozenset(
    {
        "balanced",
        "active_paper",
    }
)

SUPPORTED_OPTION_TYPES = frozenset(
    {
        "call",
        "put",
    }
)

MAX_RATIONALE_LENGTH = 240


def _normalize_rationale(value: str | None) -> str:
    if value is None:
        return "not_provided"

    if not isinstance(value, str):
        raise ValueError(
            "ai_recommendation_schema_invalid"
        )

    normalized = " ".join(value.split())

    if not normalized:
        raise ValueError(
            "ai_recommendation_schema_invalid"
        )

    return normalized[:MAX_RATIONALE_LENGTH]


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
                f"option_type={quote.option_type}, "
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

    judgment_context = ""

    if activity_mode == "balanced":
        judgment_context = (
            "\nBALANCED JUDGMENT:\n"
            "Treat all supplied daily and intraday market indicators "
            "as evidence to weigh together, not as independent hard "
            "vetoes or automatic trade triggers.\n"
            "A single FAIL, or any fixed combination of FAIL values, "
            "does not automatically require decision=NO_TRADE.\n"
            "Likewise, positive intraday momentum does not "
            "automatically require decision=TRADE.\n"
            "Negative intraday momentum does not automatically require "
            "decision=TRADE either.\n"
            "If the combined evidence is bullish, you may choose a "
            "defined-risk bull call debit spread. If the combined "
            "evidence is bearish, you may choose a defined-risk bear "
            "put debit spread.\n"
            "Choose TRADE or NO_TRADE from the combined market "
            "evidence and candidate quality. Preserve uncertainty: "
            "NO_TRADE remains appropriate when neither direction "
            "justifies a defined-risk position.\n"
        )

    activity_context = ""

    if activity_mode == "active_paper":
        activity_context = (
            "\nACTIVE PAPER MODE:\n"
            "This is an Alpaca PAPER account. The goal is to "
            "exercise the complete autonomous trading loop and "
            "collect realistic paper performance data while all "
            "Lockean limits remain unchanged.\n"
            "Prefer decision=TRADE when at least one candidate pair "
            "forms a sensible defined-risk debit vertical, its quoted "
            "debit appears likely to fit the supplied maximum-loss "
            "context, and the directional market evidence supports "
            "the structure.\n"
            "Use a bull call debit spread for bullish evidence and a "
            "bear put debit spread for bearish evidence.\n"
            "Treat individual PASS/FAIL market signals as context, "
            "not independent hard vetoes. A single FAIL does not "
            "by itself require NO_TRADE.\n"
            "Favor reasonably tight, liquid-looking candidate "
            "spreads and narrower strike widths when several "
            "choices are comparable.\n"
            "Use decision=NO_TRADE when the candidates are clearly "
            "poor, structurally unsuitable, directionally ambiguous, "
            "or the combined market evidence is materially adverse.\n"
            "You still have no permission or broker authority. "
            "Lockean independently reconstructs pricing and risk "
            "and may reject any proposal.\n"
        )

    return (
        "You are the trading agent.\n\n"
        "You decide whether the market opportunity "
        "justifies a trade and, if so, its direction.\n\n"
        "You may propose exactly one defined-risk SPY debit vertical "
        "using the candidate options below: a bullish bull call spread "
        "or a bearish bear put spread.\n"
        "For a bull call, set option_type=call, buy the lower strike, "
        "and sell the higher strike.\n"
        "For a bear put, set option_type=put, buy the higher strike, "
        "and sell the lower strike.\n"
        "If you want to propose one of those structures, "
        "set decision=TRADE.\n"
        "If you do not want to trade, "
        "set decision=NO_TRADE.\n\n"
        "Return JSON only with exactly these fields:\n"
        "decision\n"
        "symbol\n"
        "expiration\n"
        "buy_strike\n"
        "sell_strike\n"
        "contracts\n"
        "option_type\n"
        "rationale\n\n"
        "For decision=NO_TRADE, symbol, expiration, buy_strike, "
        "sell_strike, contracts, and option_type must all be null.\n"
        "For decision=TRADE, populate those fields using only the "
        "candidate options below and set option_type to call or put.\n"
        "rationale must be one short sentence explaining the market "
        "evidence behind your decision and chosen direction. Do not "
        "include permission, broker instructions, or independent risk "
        "calculations in the rationale.\n\n"
        "Do not return pricing, risk calculations, "
        "permission decisions, or broker instructions.\n"
        f"{policy_context}"
        f"{market_context_text}"
        f"{judgment_context}"
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
        self.last_decision: str | None = None
        self.last_decision_rationale: str | None = None

    def __call__(
        self,
        candidate_quotes: tuple[
            OptionQuoteSnapshot,
            ...,
        ],
        market_context: dict[str, str] | None = None,
    ) -> SpreadRecommendation | None:
        self.last_decision = None
        self.last_decision_rationale = None

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

        if not isinstance(parsed, dict):
            raise ValueError(
                "ai_recommendation_schema_invalid"
            )

        rationale = _normalize_rationale(
            parsed.get("rationale")
        )

        if "rationale" in parsed:
            parsed = {
                key: value
                for key, value in parsed.items()
                if key != "rationale"
            }

        parsed_fields = frozenset(parsed.keys())

        if parsed_fields in {
            NO_TRADE_RESPONSE_FIELDS,
            DIRECTIONAL_NO_TRADE_RESPONSE_FIELDS,
        }:
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

                if (
                    "option_type" in parsed
                    and parsed["option_type"] is not None
                ):
                    raise ValueError(
                        "ai_recommendation_schema_invalid"
                    )

                self.last_decision = "NO_TRADE"
                self.last_decision_rationale = rationale
                return None

            if decision == "TRADE":
                parsed = {
                    key: value
                    for key, value in parsed.items()
                    if key != "decision"
                }
                self.last_decision = "TRADE"
                self.last_decision_rationale = rationale

            else:
                raise ValueError(
                    "ai_recommendation_schema_invalid"
                )

        parsed_fields = frozenset(parsed.keys())
        if parsed_fields not in {
            REQUIRED_RESPONSE_FIELDS,
            DIRECTIONAL_REQUIRED_RESPONSE_FIELDS,
        }:
            raise ValueError(
                "ai_recommendation_schema_invalid"
            )

        option_type = parsed.get(
            "option_type",
            "call",
        )

        if option_type not in SUPPORTED_OPTION_TYPES:
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

        if self.last_decision is None:
            self.last_decision = "TRADE"
            self.last_decision_rationale = rationale

        return SpreadRecommendation(
            proposal_id=proposal_id,
            symbol=symbol,
            expiration=expiration,
            buy_strike=buy_strike,
            sell_strike=sell_strike,
            contracts=contracts,
            option_type=option_type,
        )
