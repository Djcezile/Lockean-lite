import argparse
from datetime import (
    date,
    datetime,
    timezone,
)
from decimal import Decimal
from uuid import uuid4

from alpaca.data.historical import (
    OptionHistoricalDataClient,
    StockHistoricalDataClient,
)

from lockean_lite.ai_recommendation_provider import (
    StructuredAIRecommendationProvider,
)
from lockean_lite.alpaca_client_factory import (
    create_paper_trading_client_from_environment,
)
from lockean_lite.alpaca_credentials import (
    load_alpaca_credentials_from_environment,
)
from lockean_lite.alpaca_option_quote_adapter import (
    read_spy_call_candidate_quotes,
)
from lockean_lite.evidence_ingestion import (
    read_cboe_vix_daily_evidence,
    read_spy_daily_evidence,
)
from lockean_lite.openai_recommendation_model import (
    create_openai_recommendation_model,
)
from lockean_lite.vix_history_source import (
    fetch_official_vix_history,
)

from lockean_lite.agent_market_context import (
    build_agent_market_context,
)


DEFAULT_STRIKE_WINDOW = Decimal("20")

DEFAULT_HISTORY_START = datetime(
    2025,
    1,
    1,
    tzinfo=timezone.utc,
)


def render_live_agent_demo(
    *,
    spy_evidence,
    vix_evidence,
    candidate_count: int,
    market_context: dict[str, str],
    recommendation,
) -> str:
    lines = [
        "LOCKEAN LIVE AGENT DEMO",
        "=======================",
        "",
        (
            "SPY EVIDENCE: "
            f"{spy_evidence.evidence_id}"
        ),
        (
            "VIX EVIDENCE: "
            f"{vix_evidence.evidence_id}"
        ),
        f"AS OF: {spy_evidence.as_of}",
        (
            "CANDIDATE OPTIONS: "
            f"{candidate_count}"
        ),
        "",
        "MARKET CONTEXT DELIVERED TO AGENT:",
    ]

    for key, value in market_context.items():
        lines.append(
            f"{key}: {value}"
        )

    lines.append("")

    if recommendation is None:
        lines.append(
            "AGENT DECISION: NO_TRADE"
    )
    else:
        lines.extend(
        [
            "AGENT DECISION: TRADE",
            (
                "SYMBOL: "
                f"{recommendation.symbol}"
            ),
            (
                "EXPIRATION: "
                f"{recommendation.expiration}"
            ),
            (
                "BUY STRIKE: "
                f"{recommendation.buy_strike}"
            ),
            (
                "SELL STRIKE: "
                f"{recommendation.sell_strike}"
            ),
            (
                "CONTRACTS: "
                f"{recommendation.contracts}"
            ),
        ]
    )

    lines.extend(
        [
            "",
            "LOCKEAN AUTHORITY INVOKED: NO",
            "EXECUTION GATEWAY INVOKED: NO",
            "BROKER ORDER SUBMITTED: NO",
        ]
    )

    return "\n".join(
        lines
    )


def run_live_agent_demo(
    *,
    spy_evidence,
    vix_evidence,
    candidate_quotes_provider,
    recommendation_provider,
    market_context_builder=None,
) -> str:

    if market_context_builder is None:
        market_context_builder = (
            build_agent_market_context
        )

    market_context = (
        market_context_builder(
            spy_evidence=spy_evidence,
            vix_evidence=vix_evidence,
        )
    )

    candidate_quotes = (
        candidate_quotes_provider()
    )

    recommendation = (
        recommendation_provider(
            candidate_quotes,
            market_context=market_context,
        )
    )

    return render_live_agent_demo(
        spy_evidence=spy_evidence,
        vix_evidence=vix_evidence,
        candidate_count=len(
            candidate_quotes
        ),
        market_context=market_context,
        recommendation=recommendation,
    )


def run_real_live_agent_demo(
    *,
    completed_through: date,
    expiration: date,
    maximum_allowed_loss: Decimal,
    proposal_id_provider=None,
    strike_window: Decimal = DEFAULT_STRIKE_WINDOW,
) -> str:
    if proposal_id_provider is None:
        proposal_id_provider = (
            lambda: str(uuid4())
        )

    credentials = (
        load_alpaca_credentials_from_environment()
    )

    stock_client = StockHistoricalDataClient(
        credentials.api_key,
        credentials.secret_key,
    )

    option_data_client = (
        OptionHistoricalDataClient(
            credentials.api_key,
            credentials.secret_key,
        )
    )

    trading_client = (
        create_paper_trading_client_from_environment()
    )

    vix_csv_text = (
        fetch_official_vix_history()
    )

    spy_evidence = read_spy_daily_evidence(
        client=stock_client,
        completed_through=completed_through,
        start=DEFAULT_HISTORY_START,
    )

    vix_evidence = (
        read_cboe_vix_daily_evidence(
            csv_text=vix_csv_text,
            completed_through=completed_through,
        )
    )

    model = (
        create_openai_recommendation_model()
    )

    recommendation_provider = (
        StructuredAIRecommendationProvider(
            proposal_id_provider=(
                proposal_id_provider
            ),
            model_callable=model,
            maximum_allowed_loss=(
                maximum_allowed_loss
            ),
        )
    )

    latest_spy_close = (
        spy_evidence.bars[-1].close
    )

    minimum_strike = (
        latest_spy_close
        - strike_window
    ).quantize(
        Decimal("1")
    )

    maximum_strike = (
        latest_spy_close
        + strike_window
    ).quantize(
        Decimal("1")
    )


    def candidate_quotes_provider():
        return read_spy_call_candidate_quotes(
            trading_client=trading_client,
            option_data_client=(
                option_data_client
            ),
            expiration=expiration,
            minimum_strike=(
                minimum_strike
            ),
            maximum_strike=(
                maximum_strike
            ),
        )

    return run_live_agent_demo(
        spy_evidence=spy_evidence,
        vix_evidence=vix_evidence,
        candidate_quotes_provider=(
            candidate_quotes_provider
        ),
        recommendation_provider=(
            recommendation_provider
        ),
    )


def main(
    argv=None,
) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the read-only Lockean Lite "
            "live AI agent demo."
        ),
    )

    parser.add_argument(
        "--completed-through",
        required=True,
        type=date.fromisoformat,
        help=(
            "Completed market session "
            "in YYYY-MM-DD format."
        ),
    )

    parser.add_argument(
        "--expiration",
        required=True,
        type=date.fromisoformat,
        help=(
            "Option expiration "
            "in YYYY-MM-DD format."
        ),
    )

    parser.add_argument(
        "--maximum-allowed-loss",
        type=Decimal,
        default=Decimal("150.00"),
        help=(
            "Lockean policy context supplied "
            "to the AI. Default: 150.00"
        ),
    )

    args = parser.parse_args(
        argv
    )

    output = run_real_live_agent_demo(
        completed_through=(
            args.completed_through
        ),
        expiration=args.expiration,
        maximum_allowed_loss=(
            args.maximum_allowed_loss
        ),
    )

    print(
        output
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )