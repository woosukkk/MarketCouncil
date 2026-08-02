import json
from datetime import datetime
from typing import Any

from openai import OpenAI

from agents.report_prompt import HUMAN_READABLE_REPORT_PROMPT
from config import MODEL_NAME, OPENAI_API_KEY


class HumanReadableReportAgent:
    def __init__(self, client: OpenAI | None = None) -> None:
        self.client = client or OpenAI(api_key=OPENAI_API_KEY)

    def generate(self, analysis_data: dict[str, Any]) -> str:
        input_data = {
            "company_name": analysis_data.get("company_name", ""),
            "analysis_time": datetime.now().isoformat(timespec="seconds"),
            "judge_result": analysis_data.get("judge_result", ""),
            "analysis_axes": analysis_data.get("analysis_axes", []),
            "axis_judgment": analysis_data.get("axis_judgment", {}),
            "axis_changes": analysis_data.get("axis_changes", []),
            "sentiment_result": analysis_data.get("sentiment_result", {}),
            "bull_result": analysis_data.get("bull_result", ""),
            "bear_result": analysis_data.get("bear_result", ""),
            "analysis_debate": analysis_data.get("analysis_debate", {}),
            "debate_applied": analysis_data.get("debate_applied", False),
        }
        input_text = (
            "다음 분석 데이터를 사람이 읽기 쉬운 최종 Markdown 보고서로 "
            "편집하라.\n\n"
            + json.dumps(input_data, ensure_ascii=False, indent=2, default=str)
        )
        last_error: Exception | None = None
        for token_limit in (6000, 12000):
            try:
                response = self.client.responses.create(
                    model=MODEL_NAME,
                    instructions=HUMAN_READABLE_REPORT_PROMPT,
                    input=input_text,
                    reasoning={"effort": "minimal"},
                    max_output_tokens=token_limit,
                )
                self._ensure_complete(response)
                markdown = self._clean_markdown(response.output_text)
                self._validate(
                    markdown,
                    debate_present=bool(
                        analysis_data.get("analysis_debate")
                    ),
                )
                return markdown
            except ValueError as error:
                last_error = error
                if token_limit == 6000:
                    print(
                        "[WARN] 최종 Markdown 보고서 응답이 불완전하여 "
                        "12000 토큰으로 재시도합니다."
                    )
                    continue
            except Exception as error:
                raise RuntimeError(
                    f"최종 Markdown 보고서 생성에 실패했습니다: {error}"
                ) from error
        raise RuntimeError(
            f"최종 Markdown 보고서 형식 검증에 실패했습니다: {last_error}"
        ) from last_error

    @staticmethod
    def _clean_markdown(value: Any) -> str:
        markdown = str(value or "").strip()
        if markdown.startswith("```") and markdown.endswith("```"):
            lines = markdown.splitlines()
            markdown = "\n".join(lines[1:-1]).strip()
        return markdown

    @staticmethod
    def _validate(markdown: str, debate_present: bool = False) -> None:
        if not markdown.startswith("# "):
            raise ValueError("Markdown 제목이 없습니다.")
        if "## 한눈에 보는 최종 판단" not in markdown:
            raise ValueError("최종 판단 섹션이 없습니다.")
        if "## 뉴스 민심" not in markdown:
            raise ValueError("뉴스 민심 섹션이 없습니다.")
        if "## 최종 결론" not in markdown:
            raise ValueError("최종 결론 섹션이 없습니다.")
        if debate_present and "## 토론 시각화" not in markdown:
            raise ValueError("토론 시각화 섹션이 없습니다.")
        if markdown.lstrip().startswith(("{", "[")):
            raise ValueError("JSON이 그대로 출력되었습니다.")
        forbidden = (
            '"positive_count"',
            '"negative_count"',
            '"analysis_debate"',
            "Bull Agent",
            "Bear Agent",
            "## 추가 확인 데이터",
            "## 추가 필요 증거",
        )
        found = next((value for value in forbidden if value in markdown), None)
        if found:
            raise ValueError(f"사용자용 보고서 금지 표현이 포함됐습니다: {found}")

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
