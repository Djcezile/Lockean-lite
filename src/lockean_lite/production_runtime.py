import os

from datetime import date
from decimal import Decimal
from uuid import uuid4

from alpaca.data.historical import (
    OptionHistoricalDataClient,
)

from lockean_lite.ai_recommendation_provider import (
    StructuredAIRecommendationProvider,
)
from lockean_lite.alpaca_cli_account_reader import (
    read_paper_account_snapshot_from_cli,
)
from lockean_lite.alpaca_client_factory import (
    create_paper_trading_client_from_environment,
)
from lockean_lite.alpaca_option_quote_adapter import (
    read_spy_call_candidate_quotes,
)
from lockean_lite.autonomous_cycle import (
    run_autonomous_trade_cycle,
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


DEFAULT_STRIKE_WINDOW = Decimal("20")


def run_production_autonomous_cycle(
    *,
    spy_evidence,
    vix_evidence,
    expiration: date,
    maximum_allowed_loss: Decimal,
    authorization_signing_key: bytes,
    proposal_id_provider=None,
    strike_window: Decimal = DEFAULT_STRIKE_WINDOW,
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
            read_paper_account_snapshot_from_cli
        ),
        authority=authority,
        execution_gateway=(
            execution_gateway
        ),
    )