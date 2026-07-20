import json
from typing import Any

from openai import OpenAI

from bull_prompt import SOURCE_COLLECTION_PROMPT
from config import MODEL_NAME, OPENAI_API_KEY


class SourceCollector:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=OPENAI_API_KEY)

    def collect(self, company_name: str) -> dict[str, Any]:
        try:
            response = self.client.responses.create(
                model=MODEL_NAME,
                instructions=SOURCE_COLLECTION_PROMPT,
                tools=[
                    {
                        "type": "web_search",
                        "search_context_size": "medium",
                    }
                ],
                input=f"{company_name} 관련 최신 주요 뉴스를 수집해줘.",
            )
        except Exception as error:
            raise RuntimeError("통합 뉴스 수집에 실패했습니다.") from error

        return self._parse_json(response.output_text)

    @staticmethod
    def _parse_json(output_text: str) -> dict[str, Any]:
        text = output_text.strip()

        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1]).strip()

        try:
            result = json.loads(text)
        except json.JSONDecodeError as error:
            raise ValueError(
                "통합 뉴스 수집 결과가 올바른 JSON이 아닙니다."
            ) from error

        if not isinstance(result, dict):
            raise ValueError("통합 뉴스 수집 결과는 JSON 객체여야 합니다.")

        articles = result.get("articles", [])
        if not isinstance(articles, list):
            result["articles"] = []
        else:
            result["articles"] = articles[:10]

        return result
