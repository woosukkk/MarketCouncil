import asyncio
from typing import Any
from urllib.parse import unquote, urlsplit


class Crawl4AIExtractor:
    MAX_CONTENT_CHARS = 1200
    MAX_CONCURRENCY = 4

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
        async with AsyncWebCrawler(config=browser_config) as crawler:
            semaphore = asyncio.Semaphore(self.MAX_CONCURRENCY)
            outcomes = await asyncio.gather(*[
                self._extract_one(crawler, candidate, run_config, semaphore)
                for candidate in candidates
            ])

        extracted = [
            document
            for document, _ in outcomes
            if document is not None
        ]
        failed = [
            failure
            for _, failure in outcomes
            if failure is not None
        ]

        return extracted, failed

    async def _extract_one(
        self,
        crawler: Any,
        candidate: dict[str, Any],
        run_config: Any,
        semaphore: Any,
    ) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
        url = str(candidate.get("url", ""))
        if (
            "youtube.com/" in url
            or "youtu.be/" in url
            or self._looks_like_document_download(url)
        ):
            return ({
                **candidate,
                "content": candidate.get("snippet", ""),
                "extraction_method": "search_snippet",
            }, None)

        try:
            async with semaphore:
                result = await crawler.arun(url=url, config=run_config)
            if not getattr(result, "success", False):
                raise RuntimeError(
                    str(getattr(result, "error_message", "수집 실패"))
                )
            metadata = getattr(result, "metadata", {}) or {}
            markdown = self._markdown_text(getattr(result, "markdown", ""))
            return ({
                **candidate,
                "title": str(
                    metadata.get("title") or candidate.get("title", "")
                ),
                "published_date": str(
                    metadata.get("article:published_time")
                    or metadata.get("date")
                    or candidate.get("published_date", "")
                ),
                "content": markdown[: self.MAX_CONTENT_CHARS],
                "extraction_method": "crawl4ai",
            }, None)
        except Exception as error:
            crawl_error = str(error)
            try:
                content = await asyncio.to_thread(
                    self._read_with_agent_reach,
                    url,
                )
                if content:
                    return ({
                        **candidate,
                        "content": content[: self.MAX_CONTENT_CHARS],
                        "extraction_method": "agent_reach_jina",
                    }, None)
            except Exception as fallback_error:
                crawl_error = (
                    f"Crawl4AI: {crawl_error}; "
                    f"Agent Reach: {fallback_error}"
                )

            snippet = str(candidate.get("snippet", ""))
            fallback = None
            if snippet:
                fallback = {
                    **candidate,
                    "content": snippet,
                    "extraction_method": "search_snippet_fallback",
                }
            return fallback, {"url": url, "reason": crawl_error}

    @staticmethod
    def _read_with_agent_reach(url: str) -> str:
        try:
            from agent_reach.channels.web import WebChannel
        except ImportError as error:
            raise RuntimeError(
                "Agent Reach is not installed. Install requirements.txt."
            ) from error

        return WebChannel().read(url).strip()

    @staticmethod
    def _markdown_text(markdown: Any) -> str:
        if isinstance(markdown, str):
            return markdown.strip()
        for attribute in ("fit_markdown", "raw_markdown"):
            value = getattr(markdown, attribute, "")
            if isinstance(value, str) and value.strip():
                return value.strip()
        return str(markdown or "").strip()

    @staticmethod
    def _looks_like_document_download(url: str) -> bool:
        decoded_url = unquote(url).lower()
        parts = urlsplit(decoded_url)
        return (
            parts.path.endswith((".pdf", ".hwp", ".doc", ".docx"))
            or ".pdf" in parts.query
            or "/download/" in parts.path
            or parts.path.endswith("download.cmd")
            or "cmd=down" in parts.query
        )
