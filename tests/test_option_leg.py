from datetime import date
from decimal import Decimal

import pytest

from lockean_lite.option_leg import OptionLeg


def test_option_leg_is_immutable_structured_intent():
    leg = OptionLeg(
        option_type="call",
        strike=Decimal("500"),
        expiration=date(2026, 9, 18),
        side="buy",
    )

    assert leg.option_type == "call"
    assert leg.strike == Decimal("500")
    assert leg.expiration == date(2026, 9, 18)
    assert leg.side == "buy"

    with pytest.raises(AttributeError):
        leg.strike = Decimal("505")