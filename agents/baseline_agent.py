import json
from typing import Any

from openai import OpenAI

from agents.baseline_prompt import (
    BASELINE_EVIDENCE_REVIEW_PROMPT,
    BASELINE_SYSTEM_PROMPT,
)
from config import MODEL_NAME, OPENAI_API_KEY


class BaselineAgent:
    def __init__(self, client: OpenAI | None = None) -> None:
        self.client = client or OpenAI(api_key=OPENAI_API_KEY)

    def analyze_with_context(
        self,
        company_name: str,
        financial_data: dict,
        report_context: str,
        web_context: str,
    ) -> str:
        user_prompt = f"""
다음 기업의 현재 상태와 확인된 추세를 정리해줘.

기업명: {company_name}

[공통 금융 데이터]

{financial_data}

[통합 로컬 투자 리포트]

{report_context}

[통합 최신 웹 근거]

{web_context}

제공된 자료만 사용해서 정리해줘.
긍정과 부정 방향을 모두 검토하되 특정 방향을 선택하지 마.
웹 근거를 사용할 때는 출처와 게시일을 표시해.
""".strip()

        try:
            response = self.client.responses.create(
                model=MODEL_NAME,
                instructions=BASELINE_SYSTEM_PROMPT,
                input=user_prompt,
            )
        except Exception as error:
            raise RuntimeError(
                f"Baseline 기준선 생성에 실패했습니다: {error}"
            ) from error

        return response.output_text

    def review_debate_evidence(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        schema = {
            "type": "object",
            "properties": {
                "claim_reviews": {
                    "type": "array",
                    "maxItems": 6,
                    "items": {
                        "type": "object",
                        "properties": {
                            "issue_id": {"type": "string"},
                            "side": {
                                "type": "string",
                                "enum": ["bull", "bear"],
                            },
                            "claim": {"type": "string"},
                            "status": {
                                "type": "string",
                                "enum": [
                                    "VERIFIED",
                                    "PARTIALLY_VERIFIED",
                                    "HYPOTHESIS",
                                    "EXPECTATION",
                                    "CONTRADICTED",
                                    "UNVERIFIABLE",
                                    "DUPLICATE",
                                ],
                            },
                            "supported_parts": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "unsupported_parts": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "conflicting_evidence": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "missing_evidence": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "required": [
                            "issue_id",
                            "side",
                            "claim",
                            "status",
                            "supported_parts",
                            "unsupported_parts",
                            "conflicting_evidence",
                            "missing_evidence",
                        ],
                        "additionalProperties": False,
                    },
                },
                "summary": {"type": "string"},
            },
            "required": ["claim_reviews", "summary"],
            "additionalProperties": False,
        }
        last_error: Exception | None = None
        for attempt in range(2):
            token_limit = 2500 * (attempt + 1)
            try:
                response = self.client.responses.create(
                    model=MODEL_NAME,
                    instructions=BASELINE_EVIDENCE_REVIEW_PROMPT,
                    text={
                        "format": {
                            "type": "json_schema",
                            "name": "baseline_evidence_review",
                            "strict": True,
                            "schema": schema,
                        }
                    },
                    input=json.dumps(
                        payload,
                        ensure_ascii=False,
                        default=str,
                    ),
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
                    continue
            except Exception as error:
                raise RuntimeError(
                    f"Baseline 증거 판별에 실패했습니다: {error}"
                ) from error

        raise RuntimeError(
            f"Baseline 증거 판별 JSON 생성에 실패했습니다: "
            f"{last_error}"
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
