import json
import time
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from openai import OpenAI

from config import MODEL_NAME, OPENAI_API_KEY, SEARXNG_URL
from tools.open_source_web_collector import OpenSourceWebCollector
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
        self.web_collector = OpenSourceWebCollector(SEARXNG_URL)

    def collect(
        self,
        company_name: str,
        ticker: str | None = None,
    ) -> dict[str, Any]:
        ticker_text = ticker or "티커 정보 없음"
        collected = self.web_collector.collect(company_name, ticker=ticker)
        input_text = (
            f"기업명: {company_name}\n"
            f"티커: {ticker_text}\n"
            "다음은 SearXNG와 Crawl4AI가 수집한 자료다. "
            "제공된 자료만 유형과 사건 방향별로 분류하라.\n\n"
            f"{json.dumps(collected['documents'], ensure_ascii=False)}"
        )

        result: dict[str, Any] | None = None
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                response = self.client.responses.create(
                    model=MODEL_NAME,
                    instructions=SOURCE_COLLECTION_PROMPT,
                    text={
                        "format": {
                            "type": "json_schema",
                            "name": "source_collection",
                            "strict": True,
                            "schema": SOURCE_COLLECTION_SCHEMA,
                        }
                    },
                    input=input_text,
                )
                result = self._parse_json(response.output_text)
                break
            except Exception as error:
                last_error = error
                if attempt == 0:
                    time.sleep(1)

        if result is None:
            detail = f"{type(last_error).__name__}: {last_error}"
            print(f"[WARN] 웹 자료 LLM 분류 실패: {detail}")
            print("[WARN] 메타데이터 기반 중립 분류로 계속합니다.")
            result = self._fallback_result(collected["documents"])

        normalized = self._normalize(result)
        normalized["collection_method"] = "searxng+crawl4ai"
        normalized["extraction_failures"] = collected["extraction_failures"]
        return normalized

    @staticmethod
    def _fallback_result(documents: list[dict[str, Any]]) -> dict[str, Any]:
        articles: list[dict[str, Any]] = []
        for index, document in enumerate(documents):
            url = str(document.get("url", "")).strip()
            focus = str(document.get("search_focus", "")).lower()
            if "youtube.com/" in url or "youtu.be/" in url:
                source_type = "youtube"
            else:
                source_type = {
                    "official": "official",
                    "news": "news",
                    "report": "report",
                    "commentary": "blog",
                }.get(focus, "news")

            articles.append({
                "title": str(document.get("title", "")).strip(),
                "source_type": source_type,
                "sentiment": "neutral",
                "reason": "LLM 분류 실패로 메타데이터만 사용한 임시 분류",
                "source": str(document.get("engine", "unknown")).strip()
                or "unknown",
                "published_date": str(
                    document.get("published_date", "")
                ).strip(),
                "url": url,
                "language": "other",
                "event_key": f"fallback-{index}",
                "is_primary_source": source_type == "official",
                "credibility_score": 0.2 if source_type == "blog" else 0.5,
            })

        return {
            "period": "",
            "summary": "LLM 분류 실패로 메타데이터 기반 자료를 사용함",
            "coverage": {},
            "articles": articles,
        }

    @staticmethod
    def _parse_json(output_text: str) -> dict[str, Any]:
        text = output_text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1]).strip()

        try:
            result = json.loads(text)
        except json.JSONDecodeError as error:
            raise ValueError("통합 웹 수집 결과가 올바른 JSON이 아닙니다.") from error

        if isinstance(result, list):
            return {"period": "", "summary": "", "coverage": {}, "articles": result}
        if not isinstance(result, dict):
            raise ValueError(
                "통합 웹 수집 결과 형식이 올바르지 않습니다. "
                f"응답 타입: {type(result).__name__}"
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
            normalized_url = cls._normalize_url(str(article.get("url", "")))
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

        tracking_parameters = {"fbclid", "gclid", "ref", "source"}
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
