import json
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from openai import OpenAI

from config import MODEL_NAME, OPENAI_API_KEY
from tools.source_collector_prompt import SOURCE_COLLECTION_PROMPT
from tools.source_collector_schema import SOURCE_COLLECTION_SCHEMA


class SourceCollector:
    SOURCE_LIMITS = {
        "official": 2,
        "news": 3,
        "report": 2,
        "blog": 1,
        "youtube": 2,
    }

    def __init__(self) -> None:
        self.client = OpenAI(api_key=OPENAI_API_KEY)

    def collect(
        self,
        company_name: str,
        ticker: str | None = None,
    ) -> dict[str, Any]:
        ticker_text = ticker or "티커 정보 없음"

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
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "source_collection",
                        "strict": True,
                        "schema": SOURCE_COLLECTION_SCHEMA,
                    }
                },
                input=(
                    f"기업명: {company_name}\n"
                    f"티커: {ticker_text}\n"
                    "최신 주요 자료를 소스 유형별로 균형 있게 수집해줘."
                ),
            )
        except Exception as error:
            raise RuntimeError("통합 뉴스 수집에 실패했습니다.") from error

        result = self._parse_json(response.output_text)
        return self._normalize(result)

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

        if isinstance(result, list):
            return {
                "period": "",
                "summary": "",
                "coverage": {},
                "articles": result,
            }

        if not isinstance(result, dict):
            result_type = type(result).__name__
            raise ValueError(
                "통합 뉴스 수집 결과 형식이 올바르지 않습니다. "
                f"응답 타입: {result_type}"
            )

        if "articles" not in result:
            result["articles"] = []

        return result

    @classmethod
    def _normalize(cls, result: dict[str, Any]) -> dict[str, Any]:
        articles = result.get("articles", [])
        if not isinstance(articles, list):
            articles = []

        counts = {source_type: 0 for source_type in cls.SOURCE_LIMITS}
        publisher_counts: dict[str, int] = {}
        seen_urls: set[str] = set()
        seen_events: set[str] = set()
        normalized_articles = []

        for article in articles:
            if not isinstance(article, dict):
                continue

            source_type = str(article.get("source_type", "")).lower()
            if source_type not in cls.SOURCE_LIMITS:
                continue
            if counts[source_type] >= cls.SOURCE_LIMITS[source_type]:
                continue

            source = str(article.get("source", "")).strip().lower()
            if not source or publisher_counts.get(source, 0) >= 2:
                continue

            normalized_url = cls._normalize_url(
                str(article.get("url", ""))
            )
            event_key = str(article.get("event_key", "")).strip().lower()

            if not normalized_url or normalized_url in seen_urls:
                continue
            if event_key and event_key in seen_events:
                continue

            article["url"] = normalized_url
            article["source_type"] = source_type
            article["credibility_score"] = cls._score(
                article.get("credibility_score")
            )

            normalized_articles.append(article)
            counts[source_type] += 1
            publisher_counts[source] = publisher_counts.get(source, 0) + 1
            seen_urls.add(normalized_url)
            if event_key:
                seen_events.add(event_key)

        result["articles"] = normalized_articles[:10]
        result["coverage"] = {
            **counts,
            "missing_types": [
                source_type
                for source_type, target in cls.SOURCE_LIMITS.items()
                if counts[source_type] < target
            ],
        }
        return result

    @staticmethod
    def _normalize_url(url: str) -> str:
        try:
            parts = urlsplit(url.strip())
        except ValueError:
            return ""

        if parts.scheme not in {"http", "https"} or not parts.netloc:
            return ""

        tracking_parameters = {
            "fbclid",
            "gclid",
            "ref",
            "source",
        }
        query = urlencode([
            (key, value)
            for key, value in parse_qsl(parts.query)
            if not key.lower().startswith("utm_")
            and key.lower() not in tracking_parameters
        ])

        return urlunsplit((
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path.rstrip("/"),
            query,
            "",
        ))

    @staticmethod
    def _score(value: Any) -> float:
        try:
            score = float(value)
        except (TypeError, ValueError):
            return 0.0

        return round(min(max(score, 0.0), 1.0), 2)
