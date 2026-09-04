import argparse
import os

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from alpaca.data.historical import (
    OptionHistoricalDataClient,
    StockHistoricalDataClient,
)

from lockean_lite.ai_recommendation_provider import (
    StructuredAIRecommendationProvider,
)
from lockean_lite.alpaca_account_reader import (
    read_paper_account_snapshot_from_environment,
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
from lockean_lite.autonomous_cycle import (
    run_autonomous_trade_cycle,
)
from lockean_lite.evidence_ingestion import (
    read_cboe_vix_daily_evidence,
    read_spy_daily_evidence,
)
from lockean_lite.execution_gateway import (
    PaperExecutionGatewayResult,
)
from lockean_lite.lockean_authority import (
    LockeanAuthority,
)
from lockean_lite.openai_recommendation_model import (
    create_openai_recommendation_model,
)
from lockean_lite.safe_error_reporting import (
    safe_exception_reason,
)
from lockean_lite.vix_history_source import (
    fetch_official_vix_history,
)


DEFAULT_STRIKE_WINDOW = Decimal("20")
DEFAULT_HISTORY_START = datetime(
    2025,
    1,
    1,
    tzinfo=timezone.utc,
)


class DiagnosticExecutionGateway:
    """Execution boundary that is physically incapable of broker submission."""

    def execute(
        self,
        proposal,
        receipt,
    ) -> PaperExecutionGatewayResult:
        return PaperExecutionGatewayResult(
            submitted=False,
            reason="diagnostic_execution_disabled",
        )


def run_live_entry_diagnostic(
    *,
    completed_through: date,
    expiration: date,
    maximum_allowed_loss: Decimal,
    authorization_signing_key: bytes,
    agent_activity_mode: str = "active_paper",
    proposal_id_provider=None,
):
    if not authorization_signing_key:
        raise ValueError(
            "authorization_signing_key_required"
        )

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

    trading_client = (
        create_paper_trading_client_from_environment()
    )

    option_data_client = (
        OptionHistoricalDataClient(
            credentials.api_key,
            credentials.secret_key,
        )
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

    latest_spy_close = (
        spy_evidence.bars[-1].close
    )

    minimum_strike = (
        latest_spy_close
        - DEFAULT_STRIKE_WINDOW
    ).quantize(
        Decimal("1")
    )

    maximum_strike = (
        latest_spy_close
        + DEFAULT_STRIKE_WINDOW
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
            activity_mode=(
                agent_activity_mode
            ),
        )
    )

    authority = LockeanAuthority(
        maximum_allowed_loss=(
            maximum_allowed_loss
        ),
        authorization_signing_key=(
            authorization_signing_key
        ),
    )

    return run_autonomous_trade_cycle(
        spy_evidence=spy_evidence,
        vix_evidence=vix_evidence,
        candidate_quotes_provider=(
            candidate_quotes_provider
        ),
        recommendation_provider=(
            recommendation_provider
        ),
        account_snapshot_provider=(
            read_paper_account_snapshot_from_environment
        ),
        authority=authority,
        execution_gateway=(
            DiagnosticExecutionGateway()
        ),
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Exercise Lockean Lite's live entry pipeline "
            "without permitting broker submission."
        )
    )

    parser.add_argument(
        "--completed-through",
        required=True,
        type=date.fromisoformat,
    )
    parser.add_argument(
        "--expiration",
        required=True,
        type=date.fromisoformat,
    )
    parser.add_argument(
        "--maximum-allowed-loss",
        type=Decimal,
        default=Decimal("150.00"),
    )
    parser.add_argument(
        "--activity-mode",
        choices=(
            "balanced",
            "active_paper",
        ),
        default="active_paper",
    )

    args = parser.parse_args(argv)

    signing_key_text = os.getenv(
        "LOCKEAN_AUTHORIZATION_SIGNING_KEY"
    )
    if not signing_key_text:
        print(
            "DIAGNOSTIC ERROR | ValueError | "
            "authorization_signing_key_required"
        )
        return 1

    print(
        "LOCKEAN LITE ENTRY DIAGNOSTIC"
    )
    print(
        "============================="
    )
    print(
        "BROKER EXECUTION: DISABLED"
    )

    try:
        result = run_live_entry_diagnostic(
            completed_through=(
                args.completed_through
            ),
            expiration=args.expiration,
            maximum_allowed_loss=(
                args.maximum_allowed_loss
            ),
            authorization_signing_key=(
                signing_key_text.encode("utf-8")
            ),
            agent_activity_mode=(
                args.activity_mode
            ),
        )
    except Exception as error:
        reason = safe_exception_reason(
            error
        )
        print(
            (
                "DIAGNOSTIC ERROR | "
                f"{type(error).__name__} | "
                f"{reason}"
            )
        )
        return 1

    print(
        (
            "DIAGNOSTIC RESULT: "
            f"{result.status} | "
            f"{result.reason}"
        )
    )

    if (
        result.reason
        == "diagnostic_execution_disabled"
    ):
        print(
            "ENTRY PIPELINE: REACHED AUTHORIZED EXECUTION BOUNDARY"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
