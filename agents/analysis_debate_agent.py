import json
from typing import Any

from openai import OpenAI

from agents.analysis_debate_prompt import (
    BEAR_ANALYSIS_DEBATE_PROMPT,
    BULL_ANALYSIS_DEBATE_PROMPT,
)
from config import MODEL_NAME, OPENAI_API_KEY


class AnalysisDebateAgent:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=OPENAI_API_KEY)

    def run(
        self,
        company_name: str,
        financial_data: dict[str, Any],
        bull_result: str,
        bear_result: str,
        sentiment_summary: dict[str, Any],
        video_summary: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        debate_input = self._build_input(
            company_name=company_name,
            financial_data=financial_data,
            bull_result=bull_result,
            bear_result=bear_result,
            sentiment_summary=sentiment_summary,
            video_summary=video_summary,
        )

        print("\n[Bull 전체 분석 반박 시작]")
        bull_rebuttal = self._respond(
            BULL_ANALYSIS_DEBATE_PROMPT,
            debate_input,
        )
        print("[Bull 전체 분석 반박 완료]")

        print("\n[Bear 전체 분석 반박 시작]")
        bear_rebuttal = self._respond(
            BEAR_ANALYSIS_DEBATE_PROMPT,
            debate_input,
        )
        print("[Bear 전체 분석 반박 완료]")

        return {
            "bull_rebuttal": bull_rebuttal,
            "bear_rebuttal": bear_rebuttal,
        }

    @staticmethod
    def _build_input(
        company_name: str,
        financial_data: dict[str, Any],
        bull_result: str,
        bear_result: str,
        sentiment_summary: dict[str, Any],
        video_summary: dict[str, Any] | None,
    ) -> str:
        return f"""기업명: {company_name}

[공통 금융 데이터]
{json.dumps(financial_data, ensure_ascii=False, indent=2, default=str)}

[Bull 전체 분석]
{bull_result}

[Bear 전체 분석]
{bear_result}

[뉴스 민심 요약]
{json.dumps(sentiment_summary, ensure_ascii=False, indent=2)}

[영상 관점별 요약]
{json.dumps(video_summary, ensure_ascii=False, indent=2) if video_summary else "사용하지 않음"}
"""

    def _respond(self, instructions: str, input_text: str) -> str:
        try:
            response = self.client.responses.create(
                model=MODEL_NAME,
                instructions=instructions,
                input=input_text,
                max_output_tokens=1800,
            )
        except Exception as error:
            raise RuntimeError("전체 분석 토론 LLM 호출에 실패했습니다.") from error
        return response.output_text
