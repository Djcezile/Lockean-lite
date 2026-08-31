from alpaca.trading.client import TradingClient
from lockean_lite.alpaca_credentials import (
    load_alpaca_credentials_from_environment,
)


def create_paper_trading_client(
    api_key: str,
    secret_key: str,
) -> TradingClient:
    return TradingClient(
        api_key=api_key,
        secret_key=secret_key,
        paper=True,
    )

def create_paper_trading_client_from_environment() -> TradingClient:
    credentials = load_alpaca_credentials_from_environment()

    return create_paper_trading_client(
        api_key=credentials.api_key,
        secret_key=credentials.secret_key,
    )