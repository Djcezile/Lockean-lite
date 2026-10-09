"""Small, destination-agnostic HTTPS webhook notifications."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
import json
import os
import re
import sys
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


_EVENT_CODE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_NTFY_TOPIC_PATH = re.compile(r"^/[A-Za-z0-9_-]{32,128}$")


class NotificationError(Exception):
    """Sanitized notification configuration or transport failure."""


@dataclass(frozen=True)
class AlertEvent:
    code: str
    message: str

    def __post_init__(self):
        if _EVENT_CODE.fullmatch(self.code) is None:
            raise ValueError("alert_code_invalid")
        if (
            not self.message
            or len(self.message) > 240
            or "\n" in self.message
            or "\r" in self.message
        ):
            raise ValueError("alert_message_invalid")


def build_notification_payload(
    event: AlertEvent,
    *,
    market_date: str,
) -> dict[str, str]:
    return {
        "text": (
            f"Lockean Lite alert [{event.code}] for {market_date}: "
            f"{event.message}"
        )
    }


def deliver_notification(
    webhook_url: str,
    payload: dict[str, str],
    *,
    transport=urlopen,
    timeout_seconds: float = 10,
) -> None:
    try:
        parsed = urlsplit(webhook_url)
    except Exception as error:
        raise NotificationError("notification_url_invalid") from error
    if parsed.scheme != "https" or not parsed.netloc:
        raise NotificationError("notification_url_invalid")

    is_ntfy = (parsed.hostname or "").lower() == "ntfy.sh"
    if is_ntfy:
        try:
            port = parsed.port
        except ValueError as error:
            raise NotificationError("notification_url_invalid") from error
        if (
            port is not None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or _NTFY_TOPIC_PATH.fullmatch(parsed.path) is None
        ):
            raise NotificationError("notification_url_invalid")

    if is_ntfy:
        message = payload.get("text")
        if not isinstance(message, str) or not message:
            raise NotificationError("notification_payload_invalid")
        body = message.encode("utf-8")
        headers = {
            "Content-Type": "text/plain; charset=utf-8",
            "Title": "Lockean Lite watchdog",
            "Priority": "high",
            "Tags": "warning",
            "User-Agent": "Lockean-Lite-Watchdog/1",
        }
    else:
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Lockean-Lite-Watchdog/1",
        }

    request = Request(
        webhook_url,
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        response = transport(request, timeout=timeout_seconds)
        close = getattr(response, "close", None)
        if callable(close):
            close()
    except Exception as error:
        raise NotificationError("notification_delivery_failed") from error


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", required=True)
    parser.add_argument(
        "--market-date",
        type=date.fromisoformat,
        default=date.today(),
    )
    args = parser.parse_args(argv)
    webhook_url = os.environ.get("LOCKEAN_NOTIFICATION_WEBHOOK", "").strip()
    if not webhook_url:
        print("NOTIFICATION TEST BLOCKED: destination_unavailable")
        return 2
    try:
        event = AlertEvent(
            "watchdog_test",
            "Deployment verification test; no trading failure occurred.",
        )
        deliver_notification(
            webhook_url,
            build_notification_payload(
                event,
                market_date=args.market_date.isoformat(),
            ),
        )
    except Exception:
        print("NOTIFICATION TEST FAILED: delivery_failed")
        return 3
    print("NOTIFICATION TEST DELIVERED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
