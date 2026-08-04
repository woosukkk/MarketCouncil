from pathlib import Path
from typing import Any

from rag.document_registry import (
    APPROVED_DIR,
    INBOX_DIR,
    REJECTED_DIR,
    DocumentRegistry,
)
from rag.document_validator import validate_document


class IngestionPipeline:
    def __init__(self) -> None:
        self.registry = DocumentRegistry()

    def register_inbox_document(
        self,
        file_path: Path,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        resolved_path = file_path.resolve()
        if resolved_path.parent != INBOX_DIR.resolve():
            raise ValueError("검토 문서는 documents/inbox 안에 있어야 합니다.")

        content_hash = self.registry.file_hash(resolved_path)
        existing = self.registry.find_by_hash(content_hash)
        if existing:
            return existing

        validation = validate_document(resolved_path, metadata)
        record = {
            "document_id": content_hash,
            "content_hash": content_hash,
            "filename": resolved_path.name,
            "file_path": str(resolved_path),
            "status": "pending",
            "company": str(metadata.get("company", "")).strip(),
            "ticker": str(metadata.get("ticker", "")).strip(),
            "title": str(metadata.get("title", resolved_path.stem)).strip(),
            "publisher": str(metadata.get("publisher", "")).strip(),
            "source_type": str(metadata.get("source_type", "report")).strip(),
            "source_url": str(metadata.get("source_url", "")).strip(),
            "original_file_path": str(
                metadata.get("original_file_path", "")
            ).strip(),
            "published_at": str(metadata.get("published_at", "")).strip(),
            "event_date": str(metadata.get("event_date", "")).strip(),
            "fiscal_period": str(metadata.get("fiscal_period", "")).strip(),
            "price_reference_date": str(
                metadata.get("price_reference_date", "")
            ).strip(),
            "timezone": "Asia/Seoul",
            "date_confidence": str(
                metadata.get("date_confidence", "medium")
            ).strip(),
            "collected_at": self.registry.now(),
            "approved_at": "",
            "rejected_at": "",
            "rejection_reason": "",
            "indexed_at": "",
            "validation": validation,
        }
        return self.registry.upsert(record)

    def approve(self, content_hash: str) -> dict[str, Any]:
        record = self._get_record(content_hash)
        errors = record.get("validation", {}).get("errors", [])
        if errors:
            raise ValueError("품질 오류가 있는 문서는 승인할 수 없습니다.")

        source = Path(record["file_path"])
        destination = self.registry.unique_destination(
            APPROVED_DIR,
            source.name,
        )
        source.replace(destination)
        return self.registry.update(
            content_hash,
            status="approved",
            file_path=str(destination.resolve()),
            filename=destination.name,
            approved_at=self.registry.now(),
        )

    def reject(
        self,
        content_hash: str,
        reason: str,
    ) -> dict[str, Any]:
        if not reason.strip():
            raise ValueError("거절 이유를 입력하세요.")

        record = self._get_record(content_hash)
        source = Path(record["file_path"])
        destination = self.registry.unique_destination(
            REJECTED_DIR,
            source.name,
        )
        source.replace(destination)
        return self.registry.update(
            content_hash,
            status="rejected",
            file_path=str(destination.resolve()),
            filename=destination.name,
            rejected_at=self.registry.now(),
            rejection_reason=reason.strip(),
        )

    def _get_record(self, content_hash: str) -> dict[str, Any]:
        record = self.registry.find_by_hash(content_hash)
        if not record:
            raise KeyError("등록되지 않은 문서입니다.")
        if record.get("status") != "pending":
            raise ValueError("검토 대기 상태의 문서만 처리할 수 있습니다.")
        return record
