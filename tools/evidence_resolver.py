from copy import deepcopy
from typing import Any

from rag.document_registry import DocumentRegistry
from tools.source_collector import SourceCollector


class EvidenceResolver:
    def __init__(self) -> None:
        self.registry = DocumentRegistry()

    def resolve(
        self,
        source_data: dict[str, Any],
        retrieved_chunks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        resolved = deepcopy(source_data)
        registry_by_url = self._registry_by_url()
        retrieved_document_ids, retrieved_urls = self._retrieved_evidence(
            retrieved_chunks or []
        )
        primary_evidence = []
        supporting_evidence = []

        for article in resolved.get("articles", []):
            normalized_url = SourceCollector._normalize_url(
                str(article.get("url", ""))
            )
            record = registry_by_url.get(normalized_url)

            if not record:
                article["rag_status"] = "not_collected"
                article["document_id"] = ""
                article["use_as_evidence"] = True
                supporting_evidence.append(article)
                continue

            status = str(record.get("status", "not_collected"))
            article["rag_status"] = status
            article["document_id"] = str(record.get("document_id", ""))
            document_id = str(record.get("document_id", ""))
            is_retrieved = (
                document_id in retrieved_document_ids
                or normalized_url in retrieved_urls
            )
            article["use_as_evidence"] = (
                status != "rejected"
                and not (status == "ingested" and is_retrieved)
            )

            if status == "ingested" and is_retrieved:
                primary_evidence.append({
                    "document_id": record.get("document_id", ""),
                    "title": record.get("title", ""),
                    "source_url": record.get("source_url", ""),
                    "published_at": record.get("published_at", ""),
                })
            elif article["use_as_evidence"]:
                supporting_evidence.append(article)

        resolved["evidence_bundle"] = {
            "primary_evidence": self._unique_documents(primary_evidence),
            "supporting_evidence": supporting_evidence,
        }
        return resolved

    @staticmethod
    def _retrieved_evidence(
        chunks: list[dict[str, Any]],
    ) -> tuple[set[str], set[str]]:
        document_ids: set[str] = set()
        urls: set[str] = set()

        for chunk in chunks:
            metadata = chunk.get("metadata", {})
            if not isinstance(metadata, dict):
                continue
            document_id = str(metadata.get("document_id", "")).strip()
            normalized_url = SourceCollector._normalize_url(
                str(metadata.get("source_url", ""))
            )
            if document_id:
                document_ids.add(document_id)
            if normalized_url:
                urls.add(normalized_url)

        return document_ids, urls

    def _registry_by_url(self) -> dict[str, dict[str, Any]]:
        indexed = {}
        for record in self.registry.load().values():
            normalized_url = SourceCollector._normalize_url(
                str(record.get("source_url", ""))
            )
            if normalized_url:
                indexed[normalized_url] = record
        return indexed

    @staticmethod
    def _unique_documents(
        documents: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        unique = {}
        for document in documents:
            document_id = str(document.get("document_id", ""))
            if document_id:
                unique[document_id] = document
        return list(unique.values())
