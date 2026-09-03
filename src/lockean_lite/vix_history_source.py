from urllib.error import URLError
from urllib.request import Request, urlopen


VIX_HISTORY_URL = (
    "https://cdn.cboe.com/api/global/us_indices/"
    "daily_prices/VIX_History.csv"
)


def fetch_official_vix_history() -> str:
    request = Request(
        VIX_HISTORY_URL,
        headers={
            "User-Agent": "Lockean-Lite/1.0",
        },
    )

    try:
        with urlopen(
            request,
            timeout=15,
        ) as response:
            return response.read().decode(
                "utf-8-sig"
            )
    except (
        URLError,
        OSError,
        UnicodeDecodeError,
    ) as error:
        raise ValueError(
            "vix_evidence_unavailable"
        ) from error