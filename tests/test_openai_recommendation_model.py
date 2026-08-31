from types import SimpleNamespace

import pytest

from lockean_lite.openai_recommendation_model import (
    OpenAIRecommendationModel,
)


VALID_RESPONSE = """
{
  "symbol": "SPY",
  "expiration": "2026-09-18",
  "buy_strike": "782",
  "sell_strike": "787",
  "contracts": 1
}
""".strip()


class FakeResponses:
    def __init__(
        self,
        *,
        output_text=VALID_RESPONSE,
        error=None,
    ):
        self.output_text = output_text
        self.error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)

        if self.error is not None:
            raise self.error

        return SimpleNamespace(
            output_text=self.output_text,
        )


class FakeClient:
    def __init__(
        self,
        *,
        output_text=VALID_RESPONSE,
        error=None,
    ):
        self.responses = FakeResponses(
            output_text=output_text,
            error=error,
        )


def test_openai_model_uses_strict_recommendation_schema():
    client = FakeClient()

    model = OpenAIRecommendationModel(
        client=client,
    )

    result = model(
        "recommend a spread"
    )

    assert result == VALID_RESPONSE

    assert len(
        client.responses.calls
    ) == 1

    request = client.responses.calls[0]

    assert request["model"] == (
        "gpt-5.6-terra"
    )

    assert request["input"] == (
        "recommend a spread"
    )

    assert request["store"] is False

    response_format = (
        request["text"]["format"]
    )

    assert response_format["type"] == (
        "json_schema"
    )

    assert response_format["strict"] is True

    schema = response_format["schema"]

    assert schema[
        "additionalProperties"
    ] is False

    assert set(schema["required"]) == {
        "symbol",
        "expiration",
        "buy_strike",
        "sell_strike",
        "contracts",
    }


def test_openai_model_fails_closed_on_empty_response():
    model = OpenAIRecommendationModel(
        client=FakeClient(
            output_text="",
        ),
    )

    with pytest.raises(
        ValueError,
        match="ai_model_empty_response",
    ):
        model(
            "recommend a spread"
        )


def test_openai_model_translates_api_failure_into_lockean_reason():
    model = OpenAIRecommendationModel(
        client=FakeClient(
            error=RuntimeError(
                "vendor failure"
            ),
        ),
    )

    with pytest.raises(
        ValueError,
        match="ai_model_request_failed",
    ):
        model(
            "recommend a spread"
        )