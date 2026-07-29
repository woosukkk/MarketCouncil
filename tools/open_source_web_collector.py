import asyncio
from typing import Any
from urllib.parse import urlsplit

from tools.crawl4ai_extractor import Crawl4AIExtractor
from tools.searxng_search import SearxngSearch


class OpenSourceWebCollector:
    MAX_CANDIDATES = 12
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
        identity = " ".join(
            value for value in (company_name, ticker or "") if value
        )
        searches = [
            (f'"{identity}" investor relations earnings', "general", "official"),
            (f'"{identity}" company latest news', "news", "news"),
            (f'"{identity}" industry analyst report', "general", "report"),
            (f'"{identity}" analysis interview video', "general", "commentary"),
        ]

        candidates: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        domain_counts: dict[str, int] = {}
        for query, category, search_focus in searches:
            results = self.search_client.search(
                query=query,
                limit=6,
                categories=category,
            )
            selected_for_query = 0
            for result in results:
                url = str(result.get("url", ""))
                if not url or url in seen_urls:
                    continue
                domain = (urlsplit(url).hostname or "").lower()
                if not domain or domain_counts.get(domain, 0) >= 2:
                    continue
                if domain in self.BLOCKED_DOMAINS:
                    continue
                result["search_query"] = query
                result["search_focus"] = search_focus
                candidates.append(result)
                seen_urls.add(url)
                domain_counts[domain] = domain_counts.get(domain, 0) + 1
                selected_for_query += 1
                if selected_for_query >= 3:
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
            "extraction_failures": failed,
        }
