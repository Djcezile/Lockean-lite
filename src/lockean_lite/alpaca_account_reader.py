from lockean_lite.alpaca_client_factory import (
    create_paper_trading_client_from_environment,
)


def read_paper_account_from_environment():
    client = create_paper_trading_client_from_environment()

    return client.get_account()