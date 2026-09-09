SAFE_REASON_MAX_LENGTH = 120
SAFE_REASON_CHARACTERS = frozenset(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789._:-"
)


def _is_safe_reason(reason: str) -> bool:
    if not reason:
        return False

    if len(reason) > SAFE_REASON_MAX_LENGTH:
        return False

    return not any(
        character not in SAFE_REASON_CHARACTERS
        for character in reason
    )


def safe_exception_reason(error: Exception) -> str:
    """Return a machine-safe reason without leaking free-form exception text."""
    error_type = type(error).__name__

    if error_type == "APIError":
        code = getattr(error, "code", None)
        if code is not None:
            safe_code = str(code).strip()
            if _is_safe_reason(safe_code):
                return f"alpaca_api_error:{safe_code}"

        status_code = getattr(
            error,
            "status_code",
            None,
        )
        if status_code is not None:
            safe_status = str(status_code).strip()
            if _is_safe_reason(safe_status):
                return (
                    "alpaca_api_error_status:"
                    f"{safe_status}"
                )

        return "alpaca_api_error"

    if error_type in {
        "APIConnectionError",
        "ConnectionError",
        "TimeoutError",
    }:
        return "alpaca_or_network_connection_error"

    if not isinstance(error, ValueError):
        return "unexpected_error"

    reason = str(error).strip()

    if not reason:
        return "value_error"

    if not _is_safe_reason(reason):
        return "value_error"

    return reason
