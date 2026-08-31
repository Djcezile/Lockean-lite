from lockean_lite.alpaca_client_factory import (
    create_paper_trading_client_from_environment,
)
from lockean_lite.paper_account_snapshot import (
    create_paper_account_snapshot,
)


def read_paper_account_from_environment():
    client = create_paper_trading_client_from_environment()

    return client.get_account()

def read_paper_account_snapshot_from_environment():
    account = read_paper_account_from_environment()

    return create_paper_account_snapshot(account)