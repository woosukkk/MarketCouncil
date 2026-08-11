import json
from typing import Any

from openai import OpenAI

from agents.debate_navigator_prompt import DEBATE_NAVIGATOR_PROMPT
from config import MODEL_NAME, OPENAI_API_KEY


NAVIGATION_SCHEMA = {
    "type": "object",
    "properties": {
        "overview": {"type": "string"},
        "reading_order": {
            "type": "array",
            "items": {"type": "string"},
        },
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "issue_id": {"type": "string"},
                    "title": {"type": "string"},
                    "status": {"type": "string"},
                    "core_disagreement": {"type": "string"},
                    "round_changes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "round": {"type": "integer"},
                                "bull_change": {"type": "string"},
                                "bear_change": {"type": "string"},
                                "new_evidence_ids": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "concessions": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "remaining_question": {"type": "string"},
                            },
                            "required": [
                                "round",
                                "bull_change",
                                "bear_change",
                                "new_evidence_ids",
                                "concessions",
                                "remaining_question",
                            ],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": [
                    "issue_id",
                    "title",
                    "status",
                    "core_disagreement",
                    "round_changes",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["overview", "reading_order", "issues"],
    "additionalProperties": False,
}


class DebateNavigatorAgent:
    def __init__(self, client: OpenAI | None = None) -> None:
        self.client = client or OpenAI(api_key=OPENAI_API_KEY)

    def analyze(self, debate: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "agenda": debate.get("agenda", []),
            "rounds": debate.get("rounds", []),
            "issue_statuses": debate.get("issue_statuses", []),
            "moderator_summary": debate.get("moderator_summary", {}),
        }
        try:
            response = self.client.responses.create(
                model=MODEL_NAME,
                instructions=DEBATE_NAVIGATOR_PROMPT,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "debate_navigation",
                        "strict": True,
                        "schema": NAVIGATION_SCHEMA,
                    }
                },
                input=json.dumps(payload, ensure_ascii=False, default=str),
                reasoning={"effort": "minimal"},
                max_output_tokens=5000,
            )
            self._ensure_complete(response)
            result = json.loads(response.output_text)
        except Exception as error:
            raise RuntimeError(
                f"토론 탐색 지도 생성에 실패했습니다: {error}"
            ) from error
        if not isinstance(result, dict):
            raise RuntimeError("토론 탐색 지도 응답이 JSON 객체가 아닙니다.")
        return result

    @staticmethod
    def _ensure_complete(response: Any) -> None:
        if getattr(response, "status", "completed") == "completed":
            return
        raise ValueError(
            f"응답 상태={getattr(response, 'status', '')}, "
            f"상세={getattr(response, 'incomplete_details', None)}"
        )
