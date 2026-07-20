from pathlib import Path
from typing import Any

from rag.ingestion_pipeline import IngestionPipeline
from tools.report_downloader import (
    ReportDownloader,
    ReportDownloadSkipped,
)
from tools.source_collector import SourceCollector


class ReportCandidateCollector:
    CANDIDATE_TYPES = {"official", "report"}

    def __init__(self) -> None:
        self.source_collector = SourceCollector()
        self.downloader = ReportDownloader()
        self.pipeline = IngestionPipeline()

    def collect(
        self,
        company_name: str,
        ticker: str | None = None,
    ) -> dict[str, Any]:
        source_data = self.source_collector.collect(
            company_name,
            ticker=ticker,
        )
        return self.queue_candidates(
            company_name,
            ticker or "",
            source_data,
        )

    def queue_candidates(
        self,
        company_name: str,
        ticker: str,
        source_data: dict[str, Any],
    ) -> dict[str, Any]:
        queued = []
        skipped = []
        failed = []
        existing_urls = self._existing_urls()

        for article in source_data.get("articles", []):
            source_type = str(article.get("source_type", ""))
            if source_type not in self.CANDIDATE_TYPES:
                continue

            url = SourceCollector._normalize_url(
                str(article.get("url", ""))
            )
            if not url:
                continue
            if url in existing_urls:
                skipped.append({"url": url, "reason": "already_registered"})
                continue

            downloaded_path: Path | None = None
            try:
                downloaded_path = self.downloader.download(url)
                content_hash = self.pipeline.registry.file_hash(downloaded_path)
                existing = self.pipeline.registry.find_by_hash(content_hash)
                if existing:
                    downloaded_path.unlink(missing_ok=True)
                    skipped.append({"url": url, "reason": "duplicate_file"})
                    continue

                record = self.pipeline.register_inbox_document(
                    downloaded_path,
                    {
                        "company": company_name,
                        "ticker": ticker,
                        "title": article.get("title", downloaded_path.stem),
                        "publisher": article.get("source", ""),
                        "source_type": (
                            "official_report"
                            if source_type == "official"
                            else "web_report"
                        ),
                        "source_url": url,
                        "published_at": article.get("published_date", ""),
                        "event_date": article.get("published_date", ""),
                        "date_confidence": "medium",
                    },
                )
                queued.append(record)
                existing_urls.add(url)
            except ReportDownloadSkipped as error:
                if downloaded_path and downloaded_path.exists():
                    downloaded_path.unlink(missing_ok=True)
                skipped.append({
                    "url": url,
                    "reason": str(error),
                })
            except Exception as error:
                if downloaded_path and downloaded_path.exists():
                    downloaded_path.unlink(missing_ok=True)
                failed.append({"url": url, "reason": str(error)})

        return {
            "queued": queued,
            "skipped": skipped,
            "failed": failed,
            "source_data": source_data,
        }

    def _existing_urls(self) -> set[str]:
        urls = set()
        for record in self.pipeline.registry.load().values():
            normalized_url = SourceCollector._normalize_url(
                str(record.get("source_url", ""))
            )
            if normalized_url:
                urls.add(normalized_url)
        return urls
