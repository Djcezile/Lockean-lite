from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.error import URLError
from urllib.request import Request, urlopen


VIX_HISTORY_URL = (
    "https://cdn.cboe.com/api/global/us_indices/"
    "daily_prices/VIX_History.csv"
)


@dataclass(frozen=True)
class VixHistoryRead:
    csv_text: str
    mode: str
    cache_age_seconds: int


class ResilientVixHistorySource:
    """Use a recent last-valid Cboe payload for transient outages only."""

    def __init__(
        self,
        *,
        fetcher,
        maximum_cache_age_seconds: int = 900,
        now_fn=None,
    ):
        if maximum_cache_age_seconds <= 0:
            raise ValueError("vix_cache_max_age_must_be_positive")

        self.fetcher = fetcher
        self.maximum_cache_age_seconds = maximum_cache_age_seconds
        self.now_fn = (
            now_fn
            if now_fn is not None
            else lambda: datetime.now(timezone.utc)
        )
        self._cached_text = None
        self._cached_at = None

    def read(self) -> VixHistoryRead:
        now = self.now_fn()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        else:
            now = now.astimezone(timezone.utc)

        try:
            csv_text = self.fetcher()
        except ValueError as error:
            if str(error) != "vix_evidence_unavailable":
                raise

            if self._cached_text is None or self._cached_at is None:
                raise ValueError("vix_evidence_unavailable") from error

            age_seconds = (now - self._cached_at).total_seconds()
            if (
                age_seconds < 0
                or age_seconds > self.maximum_cache_age_seconds
            ):
                raise ValueError("vix_evidence_unavailable") from error

            return VixHistoryRead(
                csv_text=self._cached_text,
                mode="cache",
                cache_age_seconds=int(age_seconds),
            )

        if not isinstance(csv_text, str) or not csv_text.strip():
            raise ValueError("vix_evidence_unavailable")

        self._cached_text = csv_text
        self._cached_at = now

        return VixHistoryRead(
            csv_text=csv_text,
            mode="live",
            cache_age_seconds=0,
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
