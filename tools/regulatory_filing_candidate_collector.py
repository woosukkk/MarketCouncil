import json
import re
from pathlib import Path
from typing import Any

from rag.document_loader import load_document_text
from rag.document_registry import INBOX_DIR
from rag.ingestion_pipeline import IngestionPipeline
from tools.source_collector import SourceCollector


class RegulatoryFilingCandidateCollector:
    def __init__(
        self,
        base_dir: Path = Path("documents/regulatory"),
    ) -> None:
        self.base_dir = base_dir
        self.pipeline = IngestionPipeline()

    def queue_available(
        self,
        provider: str,
        company_name: str,
    ) -> dict[str, list[dict[str, Any]]]:
        provider_directories = {
            "open_dart": "dart",
            "sec_edgar": "sec",
        }
        if provider not in provider_directories:
            raise ValueError(f"지원하지 않는 공시 공급자입니다: {provider}")
        provider_dir = provider_directories[provider]
        company_dir = self.base_dir / provider_dir / self._safe_name(company_name)
        queued: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []
        existing_urls = self._existing_urls()

        for metadata_path in sorted(company_dir.glob("*.metadata.json")):
            destination: Path | None = None
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                source_url = SourceCollector._normalize_url(
                    str(metadata.get("source_url", ""))
                )
                filing_id = str(metadata.get("filing_id", metadata_path.stem))
                if source_url and source_url in existing_urls:
                    skipped.append({"id": filing_id, "reason": "already_registered"})
                    continue

                original_path = Path(str(metadata.get("original_path", "")))
                if not original_path.exists():
                    raise FileNotFoundError(f"공시 원문이 없습니다: {original_path}")
                text = load_document_text(original_path).strip()
                if len(text) < 200:
                    raise ValueError("추출된 공시 본문이 200자 미만입니다.")

                destination = self.pipeline.registry.unique_destination(
                    INBOX_DIR,
                    f"{provider_dir}_{filing_id}.txt",
                )
                destination.write_text(text, encoding="utf-8")
                record = self.pipeline.register_inbox_document(
                    destination,
                    {
                        "company": metadata.get("company", company_name),
                        "ticker": metadata.get("ticker", ""),
                        "title": metadata.get("title", filing_id),
                        "publisher": metadata.get("publisher", provider),
                        "source_type": "regulatory_filing",
                        "source_url": source_url,
                        "published_at": metadata.get("filed_at", ""),
                        "event_date": (
                            metadata.get("report_date")
                            or metadata.get("filed_at", "")
                        ),
                        "fiscal_period": metadata.get("report_date", ""),
                        "date_confidence": "high",
                        "original_file_path": str(original_path.resolve()),
                    },
                )
                registered_path_text = str(record.get("file_path", "")).strip()
                if (
                    registered_path_text
                    and Path(registered_path_text).resolve()
                    != destination.resolve()
                ):
                    destination.unlink(missing_ok=True)
                    skipped.append({
                        "id": filing_id,
                        "reason": "duplicate_file",
                    })
                    continue
                queued.append(record)
                if source_url:
                    existing_urls.add(source_url)
            except Exception as error:
                if destination and destination.exists():
                    destination.unlink(missing_ok=True)
                failed.append({
                    "id": metadata_path.stem,
                    "reason": str(error),
                })

        return {"queued": queued, "skipped": skipped, "failed": failed}

    def _existing_urls(self) -> set[str]:
        urls = set()
        for record in self.pipeline.registry.load().values():
            normalized = SourceCollector._normalize_url(
                str(record.get("source_url", ""))
            )
            if normalized:
                urls.add(normalized)
        return urls

    @staticmethod
    def _safe_name(value: str) -> str:
        return re.sub(
            r"[^0-9A-Za-z가-힣._-]+",
            "_",
            value,
        ).strip("_") or "company"
