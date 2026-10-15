import asyncio
import re
from typing import Any
from urllib.parse import unquote, urlsplit

from tools.evidence_text import clean_article_text, is_navigation_text


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
            excluded_tags=["nav", "header", "footer", "aside", "form", "button"],
            excluded_selector='[role="navigation"], [role="banner"], [role="contentinfo"], .skip-link',
            word_count_threshold=1,
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
            snippet = self._snippet_document(candidate, "search_snippet")
            return snippet, None if snippet else {"url": url, "reason": "사용 가능한 본문이나 검색 요약이 없습니다."}

        try:
            async with semaphore:
                result = await crawler.arun(url=url, config=run_config)
            if not getattr(result, "success", False):
                raise RuntimeError(
                    str(getattr(result, "error_message", "수집 실패"))
                )
            metadata = getattr(result, "metadata", {}) or {}
            body = self._body_text(result)
            if not body:
                raise ValueError("기사 본문을 확보하지 못했습니다.")
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
                "content": self._limit_text(body),
                "extraction_method": "crawl4ai",
                "body_extraction_status": "article_body",
            }, None)
        except Exception as error:
            return self._snippet_document(candidate, "search_snippet_fallback"), {"url": url, "reason": str(error)}

    @classmethod
    def _snippet_document(cls, candidate: dict[str, Any], method: str) -> dict[str, Any] | None:
        snippet = clean_article_text(str(candidate.get("snippet") or ""))
        title = clean_article_text(str(candidate.get("title") or ""))
        if len(snippet) < 20 or snippet == title or is_navigation_text(snippet):
            return None
        return {**candidate, "content": cls._limit_text(snippet), "extraction_method": method,
                "body_extraction_status": "snippet_only"}

    @classmethod
    def _body_text(cls, result: Any) -> str:
        html = getattr(result, "html", "") or getattr(result, "cleaned_html", "")
        if isinstance(html, str) and html:
            body = cls._html_article_text(html)
            if body:
                return body
        return cls._markdown_text(getattr(result, "markdown", ""))

    @classmethod
    def _html_article_text(cls, html: str) -> str:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        for node in soup.select('nav, header, footer, aside, form, button, script, style, noscript, svg, '
                                '[role="navigation"], [role="banner"], [role="contentinfo"], .skip-link'):
            if node.parent is not None:
                node.decompose()
        for selector in ('[itemprop="articleBody"]', 'article', 'main', '[role="main"]', 'body'):
            nodes = soup.select(selector)
            if selector == "body" and not nodes:
                nodes = [soup]
            candidates = sorted(nodes, key=lambda node: len(node.get_text()), reverse=True)
            for candidate in candidates:
                body = BeautifulSoup(str(candidate), "html.parser")
                has_body_blocks = bool(body.find_all(["p", "table"]))
                for heading in body.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
                    if heading.name == "h1" or not has_body_blocks:
                        heading.decompose()
                    else:
                        heading.insert_before("\n")
                        heading.insert_after("\n")
                for table in body.find_all("table"):
                    if table.parent is None:
                        continue
                    rows = [" | ".join(cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"]))
                            for row in table.find_all("tr")]
                    table.replace_with("\n" + "\n".join(rows) + "\n")
                for node in body.find_all(["p", "div", "li", "section", "blockquote", "br"]):
                    node.insert_before("\n")
                    node.insert_after("\n")
                text = clean_article_text(body.get_text(" "))
                if cls._has_article_body(text):
                    return text
        return ""

    @staticmethod
    def _has_article_body(text: str) -> bool:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if any(len(line) >= 40 and re.search(r'[.!?。](?:["\'”’)]*)$', line) for line in lines):
            return True
        table_rows = [line for line in lines if "|" in line and len(line.split("|")) >= 2]
        return len(table_rows) >= 2 and any(re.search(r'\d', line) for line in table_rows)

    @classmethod
    def _markdown_text(cls, markdown: Any) -> str:
        candidates = [markdown] if isinstance(markdown, str) else [getattr(markdown, key, "") for key in ("fit_markdown", "raw_markdown")]
        for value in candidates:
            if isinstance(value, str):
                body_lines = "\n".join(line for line in value.splitlines() if not re.match(r"^\s{0,3}#{1,6}\s", line))
                if cls._has_article_body(clean_article_text(body_lines)):
                    return clean_article_text(value)
        return ""

    @classmethod
    def _limit_text(cls, text: str) -> str:
        if len(text) <= cls.MAX_CONTENT_CHARS:
            return text
        prefix = text[:cls.MAX_CONTENT_CHARS]
        boundary = prefix.rfind("\n")
        if boundary >= cls.MAX_CONTENT_CHARS // 2:
            return prefix[:boundary].rstrip()
        endings = list(re.finditer(r'[.!?。](?=\s|$)', prefix))
        if endings and endings[-1].end() >= cls.MAX_CONTENT_CHARS // 2:
            return prefix[:endings[-1].end()].rstrip()
        return prefix[:prefix.rfind(" ")].rstrip() if " " in prefix else prefix

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
