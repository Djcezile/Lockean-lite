from datetime import datetime, timedelta, timezone

import pytest

from lockean_lite.vix_history_source import (
    ResilientVixHistorySource,
)


BASE = datetime(2026, 9, 10, 14, 0, tzinfo=timezone.utc)


def test_live_vix_read_populates_cache():
    source = ResilientVixHistorySource(
        fetcher=lambda: "fresh-csv",
        maximum_cache_age_seconds=900,
        now_fn=lambda: BASE,
    )

    result = source.read()

    assert result.csv_text == "fresh-csv"
    assert result.mode == "live"
    assert result.cache_age_seconds == 0


def test_transient_failure_uses_recent_last_valid_vix_cache():
    calls = iter(["fresh-csv", ValueError("vix_evidence_unavailable")])

    def fetcher():
        value = next(calls)
        if isinstance(value, Exception):
            raise value
        return value

    times = iter([BASE, BASE + timedelta(minutes=5)])
    source = ResilientVixHistorySource(
        fetcher=fetcher,
        maximum_cache_age_seconds=900,
        now_fn=lambda: next(times),
    )

    source.read()
    result = source.read()

    assert result.csv_text == "fresh-csv"
    assert result.mode == "cache"
    assert result.cache_age_seconds == 300


def test_stale_vix_cache_fails_closed():
    calls = iter(["fresh-csv", ValueError("vix_evidence_unavailable")])

    def fetcher():
        value = next(calls)
        if isinstance(value, Exception):
            raise value
        return value

    times = iter([BASE, BASE + timedelta(minutes=16)])
    source = ResilientVixHistorySource(
        fetcher=fetcher,
        maximum_cache_age_seconds=900,
        now_fn=lambda: next(times),
    )

    source.read()

    with pytest.raises(ValueError, match="vix_evidence_unavailable"):
        source.read()


def test_cache_never_hides_first_fetch_failure():
    source = ResilientVixHistorySource(
        fetcher=lambda: (_ for _ in ()).throw(
            ValueError("vix_evidence_unavailable")
        ),
        maximum_cache_age_seconds=900,
        now_fn=lambda: BASE,
    )

    with pytest.raises(ValueError, match="vix_evidence_unavailable"):
        source.read()
