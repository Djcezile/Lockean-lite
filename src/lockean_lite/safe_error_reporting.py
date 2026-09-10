SAFE_REASON_MAX_LENGTH = 120
SAFE_REASON_CHARACTERS = frozenset(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789._:-"
)


ALPACA_MESSAGE_CLASSIFIERS = (
    ("invalid limit price", "alpaca_invalid_limit_price"),
    ("invalid limit_price", "alpaca_invalid_limit_price"),
    ("position intent", "alpaca_position_intent_invalid"),
    ("asset not found", "alpaca_asset_not_found"),
    ("rolling contracts ambiguity", "alpaca_rolling_contracts_ambiguity"),
    ("underlying asset mismatch", "alpaca_underlying_asset_mismatch"),
    ("submit mleg order is disabled", "alpaca_mleg_submit_disabled"),
    ("cancel mleg order is disabled", "alpaca_mleg_cancel_disabled"),
    ("replace mleg order is disabled", "alpaca_mleg_replace_disabled"),
    ("account not authorized to trade options", "alpaca_options_authorization_rejected"),
    ("account not eligible to trade", "alpaca_options_eligibility_rejected"),
    ("insufficient options buying power", "alpaca_insufficient_options_buying_power"),
    ("insufficient buying power", "alpaca_insufficient_buying_power"),
    ("cannot replace order", "alpaca_order_replace_conflict"),
    ("order already replaced", "alpaca_order_replace_conflict"),
    ("order parameters are not changed", "alpaca_order_replace_no_change"),
    ("leg order is already in", "alpaca_order_state_conflict"),
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


def _classify_alpaca_message(error: Exception) -> str | None:
    # Never return broker free-form text. It may include symbols, balances,
    # or other account-specific material. Only emit static Lockean reason
    # codes for recognized message families.
    message = str(error).lower()

    for fragment, reason in ALPACA_MESSAGE_CLASSIFIERS:
        if fragment in message:
            return reason

    return None


def safe_exception_reason(error: Exception) -> str:
    """Return a machine-safe reason without leaking free-form exception text."""
    error_type = type(error).__name__

    if error_type == "APIError":
        classified_reason = _classify_alpaca_message(error)
        if classified_reason is not None:
            return classified_reason

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
