import json
from typing import Any

from openai import OpenAI

from agents.moderator_prompt import (
    MODERATOR_AGENDA_PROMPT,
    MODERATOR_REVIEW_PROMPT,
    MODERATOR_SUMMARY_PROMPT,
)
from config import MODEL_NAME


AGENDA_SCHEMA = {
    "type": "object",
    "properties": {
        "agenda": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "issue_id": {"type": "string"},
                    "title": {"type": "string"},
                    "bull_claim": {"type": "string"},
                    "bear_claim": {"type": "string"},
                    "question": {"type": "string"},
                },
                "required": ["issue_id", "title", "bull_claim", "bear_claim", "question"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["agenda"],
    "additionalProperties": False,
}

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "issue_reviews": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "issue_id": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["OPEN", "CONTESTED", "RESOLVED", "STALEMATE", "UNKNOWN"],
                    },
                    "assessment": {"type": "string"},
                    "question_for_bull": {"type": "string"},
                    "question_for_bear": {"type": "string"},
                },
                "required": [
                    "issue_id", "status", "assessment",
                    "question_for_bull", "question_for_bear",
                ],
                "additionalProperties": False,
            },
        },
        "repeated_claims": {"type": "array", "items": {"type": "string"}},
        "missing_evidence": {"type": "array", "items": {"type": "string"}},
        "continue_debate": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": [
        "issue_reviews", "repeated_claims", "missing_evidence",
        "continue_debate", "reason",
    ],
    "additionalProperties": False,
}

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "agreements": {"type": "array", "items": {"type": "string"}},
        "unresolved_issues": {"type": "array", "items": {"type": "string"}},
        "required_evidence": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
    },
    "required": ["agreements", "unresolved_issues", "required_evidence", "summary"],
    "additionalProperties": False,
}


class ModeratorAgent:
    def __init__(self, client: OpenAI) -> None:
        self.client = client

    def create_agenda(self, debate_input: str) -> dict[str, Any]:
        return self._respond(
            MODERATOR_AGENDA_PROMPT,
            debate_input,
            "debate_agenda",
            AGENDA_SCHEMA,
            1000,
        )

    def review_round(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._respond(
            MODERATOR_REVIEW_PROMPT,
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            "debate_review",
            REVIEW_SCHEMA,
            1200,
        )

    def summarize(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._respond(
            MODERATOR_SUMMARY_PROMPT,
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            "debate_summary",
            SUMMARY_SCHEMA,
            1000,
        )

    def _respond(
        self,
        instructions: str,
        input_text: str,
        schema_name: str,
        schema: dict[str, Any],
        max_output_tokens: int,
    ) -> dict[str, Any]:
        try:
            response = self.client.responses.create(
                model=MODEL_NAME,
                instructions=instructions,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": schema_name,
                        "strict": True,
                        "schema": schema,
                    }
                },
                input=input_text,
                max_output_tokens=max_output_tokens,
            )
            result = json.loads(response.output_text)
        except Exception as error:
            raise RuntimeError(f"중재자 {schema_name} 호출에 실패했습니다: {error}") from error
        if not isinstance(result, dict):
            raise RuntimeError(f"중재자 {schema_name} 응답이 JSON 객체가 아닙니다.")
        return result
