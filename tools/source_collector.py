import json
import re
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from openai import OpenAI

from config import MODEL_NAME, OPENAI_API_KEY, SEARXNG_URL
from tools.open_source_web_collector import OpenSourceWebCollector
from tools.source_collector_prompt import SOURCE_COLLECTION_PROMPT
from tools.source_collector_schema import SOURCE_COLLECTION_SCHEMA


class SourceCollector:
    SOURCE_LIMITS = {
        "official": 20,
        "news": 24,
        "report": 20,
        "blog": 8,
        "youtube": 8,
    }
    ANALYSIS_LIMITS = {
        "official": 10,
        "news": 12,
        "report": 10,
        "blog": 4,
        "youtube": 4,
    }
    SENTIMENT_MINIMUMS = {
        "positive": 8,
        "negative": 8,
        "neutral": 4,
    }
    CLASSIFICATION_BATCH_SIZE = 24
    MAX_EVIDENCE_POOL = 80
    MAX_ARTICLES = 40

    def __init__(self) -> None:
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.web_collector = OpenSourceWebCollector(SEARXNG_URL)

    def collect(
        self,
        company_name: str,
        ticker: str | None = None,
    ) -> dict[str, Any]:
        ticker_text = ticker or "티커 정보 없음"
        try:
            collected = self.web_collector.collect(
                company_name,
                ticker=ticker,
            )
        except RuntimeError as error:
            reason = str(error)
            print(f"[WARN] 웹 근거 확인 불가: {reason}")
            return {
                "period": "확인 불가",
                "summary": "웹 근거 확인 불가",
                "coverage": {},
                "articles": [],
                "collection_method": "unavailable",
                "search_failures": [{"query": "", "reason": reason}],
                "extraction_failures": [],
            }
        result = self._classify_batches(
            company_name,
            ticker_text,
            collected["documents"],
        )

        normalized = self._normalize(result)
        normalized["collection_method"] = "searxng+crawl4ai"
        normalized["search_failures"] = collected.get("search_failures", [])
        normalized["extraction_failures"] = collected["extraction_failures"]
        normalized["source_documents"] = collected["documents"]
        return normalized

    def _classify_batches(
        self,
        company_name: str,
        ticker: str,
        documents: list[dict[str, Any]],
    ) -> dict[str, Any]:
        articles: list[dict[str, Any]] = []
        summaries: list[str] = []
        periods: list[str] = []

        for start in range(0, len(documents), self.CLASSIFICATION_BATCH_SIZE):
            batch = documents[start:start + self.CLASSIFICATION_BATCH_SIZE]
            input_text = (
                f"기업명: {company_name}\n"
                f"티커: {ticker}\n"
                "다음은 SearXNG와 Crawl4AI가 수집한 자료다. "
                "제공된 자료만 유형과 사건 방향별로 분류하라.\n\n"
                f"{json.dumps(batch, ensure_ascii=False)}"
            )
            classified: dict[str, Any] | None = None
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
                    classified = self._parse_json(response.output_text)
                    break
                except Exception as error:
                    last_error = error
                    if attempt == 0:
                        time.sleep(1)

            if classified is None:
                detail = f"{type(last_error).__name__}: {last_error}"
                print(f"[WARN] 웹 자료 배치 LLM 분류 실패: {detail}")
                classified = self._fallback_result(batch)

            articles.extend(classified.get("articles", []))
            summary = str(classified.get("summary", "")).strip()
            period = str(classified.get("period", "")).strip()
            if summary:
                summaries.append(summary)
            if period:
                periods.append(period)

        return {
            "period": " / ".join(dict.fromkeys(periods)),
            "summary": " ".join(summaries),
            "coverage": {},
            "articles": articles,
        }

    @staticmethod
    def _fallback_result(documents: list[dict[str, Any]]) -> dict[str, Any]:
        articles: list[dict[str, Any]] = []
        for index, document in enumerate(documents):
            url = str(document.get("url", "")).strip()
            source = (urlsplit(url).hostname or "").lower()
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
                "source": source or "unknown",
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
            publisher_limit = 5 if source_type == "official" else 3
            if not source or publisher_counts.get(source, 0) >= publisher_limit:
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

        evidence_pool = sorted(
            normalized_articles,
            key=cls._quality_score,
            reverse=True,
        )[: cls.MAX_EVIDENCE_POOL]
        result["evidence_pool"] = evidence_pool
        result["articles"] = cls._select_analysis_articles(evidence_pool)
        result["coverage"] = {
            **counts,
            "pool_count": len(evidence_pool),
            "analysis_count": len(result["articles"]),
            "missing_types": [
                source_type
                for source_type, target in cls.SOURCE_LIMITS.items()
                if counts[source_type] < target
            ],
        }
        return result

    @classmethod
    def _select_analysis_articles(
        cls,
        articles: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = []
        selected_urls: set[str] = set()
        type_counts = {source_type: 0 for source_type in cls.ANALYSIS_LIMITS}

        def add(
            article: dict[str, Any],
            enforce_type_limit: bool = True,
        ) -> bool:
            source_type = str(article.get("source_type", ""))
            url = str(article.get("url", ""))
            if (
                not url
                or url in selected_urls
                or (
                    enforce_type_limit
                    and type_counts.get(source_type, 0)
                    >= cls.ANALYSIS_LIMITS.get(source_type, 0)
                )
            ):
                return False
            selected.append(article)
            selected_urls.add(url)
            type_counts[source_type] += 1
            return True

        for sentiment, minimum in cls.SENTIMENT_MINIMUMS.items():
            for article in articles:
                if sum(
                    item.get("sentiment") == sentiment
                    for item in selected
                ) >= minimum:
                    break
                if article.get("sentiment") == sentiment:
                    add(article)

        for article in articles:
            if len(selected) >= cls.MAX_ARTICLES:
                break
            add(article)

        for article in articles:
            if len(selected) >= cls.MAX_ARTICLES:
                break
            add(article, enforce_type_limit=False)

        return selected

    @staticmethod
    def _quality_score(article: dict[str, Any]) -> float:
        score = SourceCollector._score(article.get("credibility_score")) * 4
        source_type = str(article.get("source_type", ""))
        score += {
            "official": 1.5,
            "report": 1.0,
            "news": 0.6,
            "blog": 0.2,
            "youtube": 0.1,
        }.get(source_type, 0.0)
        if article.get("is_primary_source"):
            score += 1.5
        reason = str(article.get("reason", ""))
        if re.search(r"\d", reason):
            score += 0.4

        published_date = str(article.get("published_date", "")).strip()
        if published_date:
            try:
                published = datetime.fromisoformat(
                    published_date.replace("Z", "+00:00")
                )
                if published.tzinfo is None:
                    published = published.replace(tzinfo=timezone.utc)
                age_days = max(
                    (datetime.now(timezone.utc) - published).days,
                    0,
                )
                if age_days <= 3:
                    score += 3.0
                elif age_days <= 7:
                    score += 2.5
                elif age_days <= 14:
                    score += 2.0
                elif age_days <= 30:
                    score += 1.2
                elif age_days <= 90:
                    score += 0.5
                elif age_days <= 365:
                    score += 0.1
            except ValueError:
                pass
        return score

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
