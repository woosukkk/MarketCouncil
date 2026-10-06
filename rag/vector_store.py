from datetime import datetime
from pathlib import Path
from typing import Any

from rag.chroma_client import get_chroma_client
from sentence_transformers import SentenceTransformer

from rag.document_loader import (
    DOCUMENTS_DIR,
    SUPPORTED_DOCUMENT_SUFFIXES,
    load_document_text,
    load_pdf_pages,
)
from rag.document_registry import APPROVED_DIR, DocumentRegistry
from rag.text_splitter import split_text


MODEL_NAME = "BAAI/bge-m3"
DB_PATH = "vector_db_bge_m3"
COLLECTION_NAME = "investment_reports_bge_m3"


def _published_timestamp(value: str) -> int:
    if not value:
        return 0

    try:
        return int(datetime.fromisoformat(value).timestamp())
    except ValueError:
        return 0


def _register_existing_document(
    registry: DocumentRegistry,
    file_path: Path,
    content_hash: str,
) -> dict[str, Any]:
    existing = registry.find_by_hash(content_hash)
    if existing:
        return existing

    now = registry.now()
    return registry.upsert({
        "document_id": content_hash,
        "content_hash": content_hash,
        "filename": file_path.name,
        "file_path": str(file_path.resolve()),
        "status": "approved",
        "company": "",
        "ticker": "",
        "title": file_path.stem,
        "publisher": "",
        "source_type": "legacy_report",
        "form_type": "",
        "source_url": "",
        "published_at": "",
        "event_date": "",
        "fiscal_period": "",
        "price_reference_date": "",
        "timezone": "Asia/Seoul",
        "date_confidence": "low",
        "collected_at": now,
        "approved_at": now,
        "rejected_at": "",
        "rejection_reason": "",
        "indexed_at": "",
        "validation": {
            "errors": [],
            "warnings": ["기존 문서이므로 메타데이터 확인이 필요합니다."],
        },
    })


def build_vector_store() -> None:
    registry = DocumentRegistry()
    model = SentenceTransformer(MODEL_NAME)
    client = get_chroma_client()
    collection = client.get_or_create_collection(name=COLLECTION_NAME)

    file_paths = [
        *DOCUMENTS_DIR.glob("*.pdf"),
        *(
            path
            for path in APPROVED_DIR.iterdir()
            if path.is_file()
            and path.suffix.lower() in SUPPORTED_DOCUMENT_SUFFIXES
        ),
    ]
    indexed_chunks = 0
    skipped_documents = 0

    for file_path in file_paths:
        content_hash = registry.file_hash(file_path)
        record = _register_existing_document(
            registry,
            file_path,
            content_hash,
        )

        if record.get("status") not in {"approved", "ingested"}:
            continue
        if record.get("indexed_at"):
            skipped_documents += 1
            continue

        if file_path.suffix.lower() == ".pdf":
            page_chunks = [
                (chunk, page_number)
                for page_number, page_text in enumerate(
                    load_pdf_pages(file_path),
                    1,
                )
                for chunk in split_text(page_text)
            ]
        else:
            page_chunks = [
                (chunk, 0)
                for chunk in split_text(load_document_text(file_path))
            ]
        chunks = [chunk for chunk, _ in page_chunks]
        if not chunks:
            continue

        embeddings = model.encode(chunks).tolist()
        document_id = str(record["document_id"])
        ids = [f"{document_id}_{index}" for index in range(len(chunks))]
        published_timestamp = _published_timestamp(
            str(record.get("published_at", ""))
        )
        metadatas = [
            {
                "document_id": document_id,
                "source": str(record.get("filename", file_path.name)),
                "chunk_id": index,
                "page_number": page_chunks[index][1],
                "company": str(record.get("company", "")),
                "ticker": str(record.get("ticker", "")),
                "title": str(record.get("title", "")),
                "publisher": str(record.get("publisher", "")),
                "source_type": str(record.get("source_type", "report")),
                "form_type": str(record.get("form_type", "")),
                "source_url": str(record.get("source_url", "")),
                "published_at": str(record.get("published_at", "")),
                "published_timestamp": published_timestamp,
                "event_date": str(record.get("event_date", "")),
                "fiscal_period": str(record.get("fiscal_period", "")),
                "timezone": str(record.get("timezone", "Asia/Seoul")),
                "date_confidence": str(record.get("date_confidence", "low")),
            }
            for index in range(len(chunks))
        ]

        collection.delete(where={"document_id": document_id})
        collection.upsert(
            ids=ids,
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        indexed_chunks += len(chunks)
        registry.update(
            content_hash,
            status="ingested",
            indexed_at=registry.now(),
        )

    print(
        f"벡터 DB 증분 저장 완료: {indexed_chunks}개 청크, "
        f"기존 문서 {skipped_documents}개 건너뜀"
    )


if __name__ == "__main__":
    build_vector_store()
