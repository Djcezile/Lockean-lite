import json

import pytest

from lockean_lite.automation.notification import (
    AlertEvent,
    NotificationError,
    build_notification_payload,
    deliver_notification,
)


def test_notification_payload_is_small_and_account_independent():
    payload = build_notification_payload(
        AlertEvent(
            code="heartbeat_stale",
            message="Session heartbeat stopped advancing.",
        ),
        market_date="2026-10-12",
    )

    assert payload == {
        "text": (
            "Lockean Lite alert [heartbeat_stale] for 2026-10-12: "
            "Session heartbeat stopped advancing."
        )
    }


def test_notification_requires_https_without_exposing_destination():
    with pytest.raises(NotificationError, match="notification_url_invalid") as error:
        deliver_notification(
            "http://secret.example.test/hook/value",
            {"text": "safe"},
            transport=lambda *_args, **_kwargs: None,
        )

    assert "secret.example" not in str(error.value)


def test_notification_posts_json_and_sanitizes_transport_failure():
    captured = {}

    def transport(request, *, timeout):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data)
        captured["timeout"] = timeout
        return object()

    deliver_notification(
        "https://hooks.example.test/private",
        {"text": "safe"},
        transport=transport,
        timeout_seconds=4,
    )

    assert captured == {
        "url": "https://hooks.example.test/private",
        "body": {"text": "safe"},
        "timeout": 4,
    }

    def failing_transport(*_args, **_kwargs):
        raise RuntimeError("secret response body")

    with pytest.raises(NotificationError, match="notification_delivery_failed") as error:
        deliver_notification(
            "https://hooks.example.test/private",
            {"text": "safe"},
            transport=failing_transport,
        )
    assert "secret" not in str(error.value)
