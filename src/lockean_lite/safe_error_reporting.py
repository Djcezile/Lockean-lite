SAFE_REASON_MAX_LENGTH = 120
SAFE_REASON_CHARACTERS = frozenset(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789._:-"
)


def safe_exception_reason(error: Exception) -> str:
    """Return a machine-safe reason without leaking free-form exception text."""
    if not isinstance(error, ValueError):
        return "unexpected_error"

    reason = str(error).strip()

    if not reason:
        return "value_error"

    if len(reason) > SAFE_REASON_MAX_LENGTH:
        return "value_error"

    if any(
        character not in SAFE_REASON_CHARACTERS
        for character in reason
    ):
        return "value_error"

    return reason
