from openai import OpenAI


RECOMMENDATION_SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {
            "type": "string",
            "enum": [
                "TRADE",
                "NO_TRADE",
            ],
        },
        "symbol": {
            "type": [
                "string",
                "null",
            ],
            "enum": [
                "SPY",
                None,
            ],
        },
        "expiration": {
            "type": [
                "string",
                "null",
            ],
        },
        "buy_strike": {
            "type": [
                "string",
                "null",
            ],
        },
        "sell_strike": {
            "type": [
                "string",
                "null",
            ],
        },
        "contracts": {
            "type": [
                "integer",
                "null",
            ],
            "minimum": 1,
        },
    },
    "required": [
        "decision",
        "symbol",
        "expiration",
        "buy_strike",
        "sell_strike",
        "contracts",
    ],
    "additionalProperties": False,
}


class OpenAIRecommendationModel:
    def __init__(
        self,
        *,
        client,
        model: str = "gpt-5.6-terra",
    ):
        self.client = client
        self.model = model

    def __call__(
        self,
        prompt: str,
    ) -> str:
        try:
            response = (
                self.client.responses.create(
                    model=self.model,
                    input=prompt,
                    text={
                        "format": {
                            "type": "json_schema",
                            "name": (
                                "spread_recommendation"
                            ),
                            "schema": (
                                RECOMMENDATION_SCHEMA
                            ),
                            "strict": True,
                        }
                    },
                    store=False,
                )
            )
        except Exception as error:
            raise ValueError(
                "ai_model_request_failed"
            ) from error

        output_text = (
            response.output_text
        )

        if (
            not isinstance(
                output_text,
                str,
            )
            or not output_text.strip()
        ):
            raise ValueError(
                "ai_model_empty_response"
            )

        return output_text


def create_openai_recommendation_model():
    return OpenAIRecommendationModel(
        client=OpenAI(),
    )