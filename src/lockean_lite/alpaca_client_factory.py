from alpaca.trading.client import TradingClient


def create_paper_trading_client(
    api_key: str,
    secret_key: str,
) -> TradingClient:
    return TradingClient(
        api_key=api_key,
        secret_key=secret_key,
        paper=True,
    )