import json
from typing import Any

from openai import OpenAI

from agents.regime_reason_prompt import REGIME_REASON_PROMPT
from config import MODEL_NAME, OPENAI_API_KEY


REASON_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "claim": {"type": "string"},
        "classification": {
            "type": "string",
            "enum": [
                "VERIFIED_EVENT",
                "MARKET_INTERPRETATION",
                "ANALYST_HYPOTHESIS",
            ],
        },
        "explanation": {"type": "string"},
        "evidence": {
            "type": "array",
            "maxItems": 2,
            "items": {
                "type": "object",
                "properties": {
                    "source_id": {"type": "string"},
                    "quote_id": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["source_id", "quote_id", "reason"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["claim", "classification", "explanation", "evidence"],
    "additionalProperties": False,
}

REGIME_REASON_SCHEMA = {
    "type": "object",
    "properties": {
        "past_bull": {"type": "array", "maxItems": 2, "items": REASON_ITEM_SCHEMA},
        "recent_bear": {"type": "array", "maxItems": 2, "items": REASON_ITEM_SCHEMA},
    },
    "required": ["past_bull", "recent_bear"],
    "additionalProperties": False,
}


class RegimeReasonAgent:
    def __init__(self, client: OpenAI | None = None) -> None:
        self.client = client or OpenAI(api_key=OPENAI_API_KEY)

    def analyze(self, payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        try:
            response = self.client.responses.create(
                model=MODEL_NAME,
                instructions=REGIME_REASON_PROMPT,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "regime_reasons",
                        "strict": True,
                        "schema": REGIME_REASON_SCHEMA,
                    }
                },
                input=json.dumps(payload, ensure_ascii=False, default=str),
                reasoning={"effort": "minimal"},
                max_output_tokens=4000,
            )
            if getattr(response, "status", "completed") != "completed":
                raise ValueError(str(getattr(response, "incomplete_details", None)))
            result = json.loads(response.output_text)
        except Exception as error:
            raise RuntimeError(f"국면별 이유 생성에 실패했습니다: {error}") from error
        if not isinstance(result, dict):
            raise RuntimeError("국면별 이유 응답이 JSON 객체가 아닙니다.")
        return result
