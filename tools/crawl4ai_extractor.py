from typing import Any


class Crawl4AIExtractor:
    MAX_CONTENT_CHARS = 2000

    async def extract_many(
        self,
        candidates: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        try:
            from crawl4ai import (
                AsyncWebCrawler,
                BrowserConfig,
                CacheMode,
                CrawlerRunConfig,
            )
        except ImportError as error:
            raise RuntimeError(
                "Crawl4AI가 설치되지 않았습니다. requirements.txt를 설치하세요."
            ) from error

        browser_config = BrowserConfig(headless=True, verbose=False)
        run_config = CrawlerRunConfig(
            cache_mode=CacheMode.ENABLED,
            page_timeout=30000,
            wait_until="domcontentloaded",
            remove_overlay_elements=True,
        )
        extracted: list[dict[str, Any]] = []
        failed: list[dict[str, str]] = []

        async with AsyncWebCrawler(config=browser_config) as crawler:
            for candidate in candidates:
                url = str(candidate.get("url", ""))
                if "youtube.com/" in url or "youtu.be/" in url:
                    extracted.append({
                        **candidate,
                        "content": candidate.get("snippet", ""),
                        "extraction_method": "search_snippet",
                    })
                    continue
                try:
                    result = await crawler.arun(url=url, config=run_config)
                    if not getattr(result, "success", False):
                        raise RuntimeError(
                            str(getattr(result, "error_message", "수집 실패"))
                        )
                    metadata = getattr(result, "metadata", {}) or {}
                    markdown = self._markdown_text(getattr(result, "markdown", ""))
                    extracted.append({
                        **candidate,
                        "title": str(
                            metadata.get("title")
                            or candidate.get("title", "")
                        ),
                        "published_date": str(
                            metadata.get("article:published_time")
                            or metadata.get("date")
                            or candidate.get("published_date", "")
                        ),
                        "content": markdown[: self.MAX_CONTENT_CHARS],
                        "extraction_method": "crawl4ai",
                    })
                except Exception as error:
                    snippet = str(candidate.get("snippet", ""))
                    if snippet:
                        extracted.append({
                            **candidate,
                            "content": snippet,
                            "extraction_method": "search_snippet_fallback",
                        })
                    failed.append({"url": url, "reason": str(error)})

        return extracted, failed

    @staticmethod
    def _markdown_text(markdown: Any) -> str:
        if isinstance(markdown, str):
            return markdown.strip()
        for attribute in ("fit_markdown", "raw_markdown"):
            value = getattr(markdown, attribute, "")
            if isinstance(value, str) and value.strip():
                return value.strip()
        return str(markdown or "").strip()
