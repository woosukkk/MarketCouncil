from tools.run_metrics import measure_stage
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

    @measure_stage("history")
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
        # A search query's official intent is not issuer/source verification.
        for document in verified_web:
            kind = "unknown" if document.get("search_focus") == "official" else "news"
            document.update(source_type=kind, search_focus=kind)
        return official_documents + verified_web

    def _dart_documents(self, company_name: str, ticker: str) -> list[dict[str, Any]]:
        # Filing list metadata is not a filing body. Reuse only validated local originals.
        try:
            from app.evidence_preflight import evidence_base, primary_chunks
            from tools.company_evidence_collector import CompanyEvidenceCollector
            from tools.evidence_readiness import evaluate_readiness
            manifest = CompanyEvidenceCollector(evidence_base()).load(company_name, ticker)
            report = evaluate_readiness(manifest)
            return [{"title": chunk["metadata"]["title"], "url": chunk["source"],
                     "published_date": chunk["metadata"]["published_at"],
                     "content": chunk["text"], "search_focus": "official", "source_type": "official"}
                    for chunk in primary_chunks(manifest, report)]
        except (OSError, ValueError, KeyError):
            return []

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
