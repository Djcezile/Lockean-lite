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
    PaperExecutionGateway,
)
from lockean_lite.lockean_authority import (
    LockeanAuthority,
)
from lockean_lite.openai_recommendation_model import (
    create_openai_recommendation_model,
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


def run_live_production_autonomous_cycle(
    *,
    completed_through: date,
    expiration: date,
    maximum_allowed_loss: Decimal,
    authorization_signing_key: bytes,
    proposal_id_provider=None,
    agent_activity_mode: str = "balanced",
):
    if not authorization_signing_key:
        raise ValueError(
            "authorization_signing_key_required"
        )

    credentials = (
        load_alpaca_credentials_from_environment()
    )

    stock_client = StockHistoricalDataClient(
        credentials.api_key,
        credentials.secret_key,
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

    return run_production_autonomous_cycle(
        spy_evidence=spy_evidence,
        vix_evidence=vix_evidence,
        expiration=expiration,
        maximum_allowed_loss=(
            maximum_allowed_loss
        ),
        authorization_signing_key=(
            authorization_signing_key
        ),
        proposal_id_provider=(
            proposal_id_provider
        ),
        agent_activity_mode=(
            agent_activity_mode
        ),
    )


def run_production_autonomous_cycle(
    *,
    spy_evidence,
    vix_evidence,
    expiration: date,
    maximum_allowed_loss: Decimal,
    authorization_signing_key: bytes,
    proposal_id_provider=None,
    strike_window: Decimal = DEFAULT_STRIKE_WINDOW,
    agent_activity_mode: str = "balanced",
):
    if not authorization_signing_key:
        raise ValueError(
            "authorization_signing_key_required"
        )

    if proposal_id_provider is None:
        proposal_id_provider = (
            lambda: str(uuid4())
        )

    trading_client = (
        create_paper_trading_client_from_environment()
    )

    option_data_client = (
        OptionHistoricalDataClient(
            os.environ["ALPACA_API_KEY"],
            os.environ["ALPACA_SECRET_KEY"],
        )
    )

    model = (
        create_openai_recommendation_model()
    )

    provider_kwargs = {
        "proposal_id_provider": (
            proposal_id_provider
        ),
        "model_callable": model,
        "maximum_allowed_loss": (
            maximum_allowed_loss
        ),
    }

    # Preserve the legacy balanced constructor shape for
    # existing integrations; active mode is opt-in.
    if agent_activity_mode != "balanced":
        provider_kwargs["activity_mode"] = (
            agent_activity_mode
        )

    recommendation_provider = (
        StructuredAIRecommendationProvider(
            **provider_kwargs
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

    authority = LockeanAuthority(
        maximum_allowed_loss=(
            maximum_allowed_loss
        ),
        authorization_signing_key=(
            authorization_signing_key
        ),
    )

    execution_gateway = (
        PaperExecutionGateway(
            client=trading_client,
            signing_key=(
                authorization_signing_key
            ),
        )
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
            execution_gateway
        ),
    )
