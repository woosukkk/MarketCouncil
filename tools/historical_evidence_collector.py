import asyncio
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from tools.crawl4ai_extractor import Crawl4AIExtractor
from tools.dart_collector import DartCollector
from tools.searxng_search import SearxngSearch


class HistoricalEvidenceCollector:
    MAX_DOCUMENTS = 36

    def __init__(self, searxng_url: str, dart_api_key: str | None = None) -> None:
        self.search = SearxngSearch(searxng_url)
        self.extractor = Crawl4AIExtractor()
        self.dart = (
            DartCollector(dart_api_key, Path("data/raw"))
            if dart_api_key
            else None
        )

    def collect(self, company_name: str, ticker: str) -> list[dict[str, Any]]:
        today = date.today()
        start_date = today - timedelta(days=365 * 3)
        official_documents = self._dart_documents(company_name, ticker)
        candidates: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for year in range(start_date.year, today.year + 1):
            for topic, focus in (
                ("실적 발표 IR 공시", "official"),
                ("사업보고서 주요 계약 투자", "official"),
                ("주요 사건 뉴스", "news"),
            ):
                query = f'"{company_name}" {ticker} {year} {topic}'
                try:
                    results = self.search.search(query, limit=8, time_range=None)
                except RuntimeError:
                    continue
                for result in results:
                    url = str(result.get("url", ""))
                    if not url or url in seen_urls:
                        continue
                    result.update({"search_query": query, "search_focus": focus})
                    candidates.append(result)
                    seen_urls.add(url)
                    if len(candidates) >= self.MAX_DOCUMENTS:
                        break
                if len(candidates) >= self.MAX_DOCUMENTS:
                    break
            if len(candidates) >= self.MAX_DOCUMENTS:
                break
        documents = []
        if candidates:
            documents, _ = asyncio.run(self.extractor.extract_many(candidates))
        verified_web = [
            document for document in documents
            if self._date(document.get("published_date"))
            and start_date <= self._date(document.get("published_date")) <= today
        ]
        return official_documents + verified_web

    def _dart_documents(self, company_name: str, ticker: str) -> list[dict[str, Any]]:
        if self.dart is None or not ticker.endswith((".KS", ".KQ")):
            return []
        try:
            filings = self.dart.list_history(company_name, ticker)
        except (RuntimeError, ValueError):
            return []
        return [
            {
                "title": str(filing.get("report_nm", "공시")),
                "url": (
                    "https://dart.fss.or.kr/dsaf001/main.do?rcpNo="
                    f"{filing.get('rcept_no', '')}"
                ),
                "published_date": self._dart_date(filing.get("rcept_dt", "")),
                "content": (
                    f"{filing.get('report_nm', '공시')} · "
                    f"제출인 {filing.get('flr_nm', '확인 불가')}"
                ),
                "search_focus": "official",
            }
            for filing in filings
            if filing.get("rcept_no")
            and self._dart_date(filing.get("rcept_dt", ""))
            and self._is_material_filing(filing.get("report_nm", ""))
        ]

    @staticmethod
    def _is_material_filing(value: Any) -> bool:
        title = str(value)
        return not any(excluded in title for excluded in (
            "임원ㆍ주요주주특정증권등소유상황보고서",
            "주식등의대량보유상황보고서",
        ))

    @staticmethod
    def _dart_date(value: Any) -> str:
        text = str(value).strip()
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}" if len(text) == 8 else ""

    @staticmethod
    def _date(value: Any) -> date | None:
        try:
            return datetime.fromisoformat(str(value).strip().replace("Z", "+00:00")).date()
        except ValueError:
            return None
