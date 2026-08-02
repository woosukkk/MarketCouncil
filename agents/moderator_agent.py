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
                    "axis_id": {"type": "string"},
                    "title": {"type": "string"},
                    "bull_claim": {"type": "string"},
                    "bear_claim": {"type": "string"},
                    "question": {"type": "string"},
                    "allowed_evidence_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": [
                    "issue_id", "axis_id", "title", "bull_claim",
                    "bear_claim", "question", "allowed_evidence_ids",
                ],
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
                        "enum": [
                            "OPEN", "CONTESTED", "RESOLVED", "STALEMATE",
                            "UNKNOWN", "INVALID",
                        ],
                    },
                    "assessment": {"type": "string"},
                    "question_for_bull": {"type": "string"},
                    "question_for_bear": {"type": "string"},
                    "verified_points": {
                        "type": "array", "items": {"type": "string"},
                    },
                    "rejected_points": {
                        "type": "array", "items": {"type": "string"},
                    },
                    "remaining_uncertainty": {"type": "string"},
                    "confidence_change": {
                        "type": "number", "minimum": -1.0, "maximum": 1.0,
                    },
                },
                "required": [
                    "issue_id", "status", "assessment",
                    "question_for_bull", "question_for_bear",
                    "verified_points", "rejected_points",
                    "remaining_uncertainty", "confidence_change",
                ],
                "additionalProperties": False,
            },
        },
        "repeated_claims": {"type": "array", "items": {"type": "string"}},
        "missing_evidence": {"type": "array", "items": {"type": "string"}},
        "new_evidence_ids": {"type": "array", "items": {"type": "string"}},
        "continue_debate": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": [
        "issue_reviews", "repeated_claims", "missing_evidence",
        "new_evidence_ids", "continue_debate", "reason",
    ],
    "additionalProperties": False,
}

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "agreements": {"type": "array", "items": {"type": "string"}},
        "unresolved_issues": {"type": "array", "items": {"type": "string"}},
        "required_evidence": {"type": "array", "items": {"type": "string"}},
        "axis_debate_results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "axis_id": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": [
                            "OPEN", "CONTESTED", "RESOLVED", "STALEMATE",
                            "UNKNOWN", "INVALID",
                        ],
                    },
                    "verified_points": {
                        "type": "array", "items": {"type": "string"},
                    },
                    "rejected_points": {
                        "type": "array", "items": {"type": "string"},
                    },
                    "remaining_hypotheses": {
                        "type": "array", "items": {"type": "string"},
                    },
                    "required_evidence": {
                        "type": "array", "items": {"type": "string"},
                    },
                    "confidence_change": {
                        "type": "number", "minimum": -1.0, "maximum": 1.0,
                    },
                },
                "required": [
                    "axis_id", "status", "verified_points", "rejected_points",
                    "remaining_hypotheses", "required_evidence",
                    "confidence_change",
                ],
                "additionalProperties": False,
            },
        },
        "summary": {"type": "string"},
    },
    "required": [
        "agreements", "unresolved_issues", "required_evidence",
        "axis_debate_results", "summary",
    ],
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
            2000,
        )

    def review_round(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._respond(
            MODERATOR_REVIEW_PROMPT,
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            "debate_review",
            REVIEW_SCHEMA,
            2000,
        )

    def summarize(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._respond(
            MODERATOR_SUMMARY_PROMPT,
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            "debate_summary",
            SUMMARY_SCHEMA,
            2000,
        )

    def _respond(
        self,
        instructions: str,
        input_text: str,
        schema_name: str,
        schema: dict[str, Any],
        max_output_tokens: int,
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(2):
            token_limit = max_output_tokens * (attempt + 1)
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
                    reasoning={"effort": "minimal"},
                    max_output_tokens=token_limit,
                )
                self._ensure_complete(response)
                result = json.loads(response.output_text)
                if not isinstance(result, dict):
                    raise ValueError("응답이 JSON 객체가 아닙니다.")
                return result
            except (json.JSONDecodeError, ValueError) as error:
                last_error = error
                if attempt == 0:
                    print(
                        f"[WARN] 중재자 {schema_name} 응답이 불완전하여 "
                        f"{token_limit * 2} 토큰으로 재시도합니다."
                    )
                    continue
            except Exception as error:
                raise RuntimeError(
                    f"중재자 {schema_name} 호출에 실패했습니다: {error}"
                ) from error

        raise RuntimeError(
            f"중재자 {schema_name} JSON 응답 생성에 실패했습니다: {last_error}"
        ) from last_error

    @staticmethod
    def _ensure_complete(response: Any) -> None:
        status = getattr(response, "status", "completed")
        if status == "completed":
            return
        details = getattr(response, "incomplete_details", None)
        usage = getattr(response, "usage", None)
        raise ValueError(
            f"응답 상태={status}, 상세={details}, 사용량={usage}"
        )
