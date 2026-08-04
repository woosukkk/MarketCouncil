import asyncio
from typing import Any
from urllib.parse import urlsplit

from tools.crawl4ai_extractor import Crawl4AIExtractor
from tools.searxng_search import SearxngSearch


class OpenSourceWebCollector:
    MAX_CANDIDATES = 96
    SEARCH_RESULT_LIMIT = 16
    PER_QUERY_LIMIT = 4
    BLOCKED_DOMAINS = {
        "instagram.com",
        "www.instagram.com",
        "scribd.com",
        "www.scribd.com",
        "t.me",
        "telegram.me",
    }

    def __init__(self, searxng_url: str) -> None:
        self.search_client = SearxngSearch(searxng_url)
        self.extractor = Crawl4AIExtractor()

    def collect(
        self,
        company_name: str,
        ticker: str | None = None,
    ) -> dict[str, Any]:
        company_term = f'"{company_name}"'
        ticker_term = ticker or ""
        identity = " ".join(
            value for value in (company_term, ticker_term) if value
        )
        topics = [
            ("investor relations earnings", "general", "official"),
            ("company presentation guidance", "general", "official"),
            ("company latest news", "news", "news"),
            ("industry market outlook", "general", "report"),
            ("competitors market share", "general", "report"),
            ("product technology growth", "general", "news"),
            ("risk regulation margin cost", "news", "news"),
            ("valuation consensus analysis", "general", "commentary"),
            ("supply chain raw materials capacity", "news", "news"),
            ("management capital allocation", "general", "official"),
            ("customers orders contracts", "news", "news"),
            ("interest rates foreign exchange macro", "general", "report"),
        ]
        intraday_topics = {0, 2, 5, 6, 8, 9, 10, 11}
        background_topics = {0, 3, 4, 7}
        searches = [
            (f"{identity} {topic}", category, focus, "day")
            for index, (topic, category, focus) in enumerate(topics)
            if index in intraday_topics
        ]
        searches.extend(
            (f"{identity} {topic}", category, focus, "month")
            for topic, category, focus in topics
        )
        searches.extend(
            (f"{identity} {topic}", category, focus, "year")
            for index, (topic, category, focus) in enumerate(topics)
            if index in background_topics
        )

        candidates: list[dict[str, Any]] = []
        search_failures: list[dict[str, str]] = []
        seen_urls: set[str] = set()
        domain_counts: dict[str, int] = {}
        for query, category, search_focus, time_range in searches:
            try:
                results = self.search_client.search(
                    query=query,
                    limit=self.SEARCH_RESULT_LIMIT,
                    categories=category,
                    time_range=time_range,
                )
            except RuntimeError as error:
                search_failures.append({
                    "query": query,
                    "reason": str(error),
                })
                continue
            selected_for_query = 0
            for result in results:
                url = str(result.get("url", ""))
                if not url or url in seen_urls:
                    continue
                domain = (urlsplit(url).hostname or "").lower()
                domain_limit = 6 if search_focus == "official" else 3
                if not domain or domain_counts.get(domain, 0) >= domain_limit:
                    continue
                if domain in self.BLOCKED_DOMAINS:
                    continue
                result["search_query"] = query
                result["search_focus"] = search_focus
                candidates.append(result)
                seen_urls.add(url)
                domain_counts[domain] = domain_counts.get(domain, 0) + 1
                selected_for_query += 1
                if selected_for_query >= self.PER_QUERY_LIMIT:
                    break

        candidates = candidates[: self.MAX_CANDIDATES]

        if not candidates:
            raise RuntimeError("SearXNG에서 분석할 웹 자료를 찾지 못했습니다.")

        extracted, failed = asyncio.run(
            self.extractor.extract_many(candidates)
        )
        if not extracted:
            raise RuntimeError("Crawl4AI가 웹 자료 본문을 추출하지 못했습니다.")
        return {
            "documents": extracted,
            "search_failures": search_failures,
            "extraction_failures": failed,
        }
