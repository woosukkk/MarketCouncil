import json
from typing import Any

from openai import OpenAI

from config import MODEL_NAME, OPENAI_API_KEY
from tools.report_source_prompt import REPORT_SOURCE_PROMPT
from tools.report_source_schema import REPORT_SOURCE_SCHEMA
from tools.source_collector import SourceCollector


class ReportSourceCollector:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=OPENAI_API_KEY)

    def collect(
        self,
        company_name: str,
        ticker: str | None = None,
    ) -> dict[str, Any]:
        try:
            response = self.client.responses.create(
                model=MODEL_NAME,
                instructions=REPORT_SOURCE_PROMPT,
                tools=[{
                    "type": "web_search",
                    "search_context_size": "medium",
                }],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "report_source_collection",
                        "strict": True,
                        "schema": REPORT_SOURCE_SCHEMA,
                    }
                },
                input=(
                    f"기업명: {company_name}\n"
                    f"티커: {ticker or '티커 정보 없음'}\n"
                    "공식 문서와 전문 리포트만 검색해줘."
                ),
            )
        except Exception as error:
            raise RuntimeError("리포트 전용 검색에 실패했습니다.") from error

        return self._normalize(self._parse_json(response.output_text))

    @staticmethod
    def _parse_json(output_text: str) -> dict[str, Any]:
        try:
            result = json.loads(output_text.strip())
        except json.JSONDecodeError as error:
            raise ValueError("리포트 검색 결과가 올바른 JSON이 아닙니다.") from error

        if not isinstance(result, dict):
            raise ValueError("리포트 검색 결과는 JSON 객체여야 합니다.")
        return result

    @staticmethod
    def _normalize(result: dict[str, Any]) -> dict[str, Any]:
        articles = []
        seen_urls = set()

        for report in result.get("reports", []):
            if not isinstance(report, dict):
                continue

            source_type = str(report.get("source_type", ""))
            preferred_url = str(report.get("direct_pdf_url", "")).strip()
            landing_url = str(report.get("url", "")).strip()
            normalized_url = SourceCollector._normalize_url(
                preferred_url or landing_url
            )
            if not normalized_url or normalized_url in seen_urls:
                continue

            articles.append({
                **report,
                "source_type": (
                    "official"
                    if source_type == "official_report"
                    else "report"
                ),
                "report_type": source_type,
                "url": normalized_url,
                "landing_url": SourceCollector._normalize_url(landing_url),
                "sentiment": "neutral",
                "reason": "자동 수집 후보 리포트",
                "event_key": "",
            })
            seen_urls.add(normalized_url)

        return {
            "period": result.get("period", ""),
            "summary": result.get("summary", ""),
            "articles": articles[:8],
        }
