import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AlpacaCredentials:
    api_key: str
    secret_key: str


def load_alpaca_credentials_from_environment() -> AlpacaCredentials:
    api_key = os.environ.get("ALPACA_API_KEY")
    secret_key = os.environ.get("ALPACA_SECRET_KEY")

    if not api_key:
        raise ValueError(
            "missing_alpaca_credentials: ALPACA_API_KEY"
        )

    if not secret_key:
        raise ValueError(
            "missing_alpaca_credentials: ALPACA_SECRET_KEY"
        )

    return AlpacaCredentials(
        api_key=api_key,
        secret_key=secret_key,
    )