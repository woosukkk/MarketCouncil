import json
from copy import deepcopy
from typing import Any
from urllib.parse import urlsplit


class EvidenceCatalog:
    MAX_WEB_DOCUMENTS = 16

    @classmethod
    def build(
        cls,
        financial_data: dict[str, Any],
        retrieved_chunks: list[dict[str, Any]],
        web_documents: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        entries = [cls._financial_entry(financial_data)]
        seen_chunks: set[tuple[str, str]] = set()

        for chunk in retrieved_chunks:
            metadata = chunk.get("metadata", {})
            if not isinstance(metadata, dict):
                metadata = {}
            key = (
                str(metadata.get("document_id", chunk.get("source", ""))),
                str(chunk.get("chunk_id", metadata.get("chunk_id", ""))),
            )
            if key in seen_chunks:
                continue
            seen_chunks.add(key)
            entries.append({
                "source_id": f"RAG-{len(seen_chunks):03d}",
                "source_type": str(metadata.get("source_type", "report")),
                "title": str(
                    metadata.get("title")
                    or metadata.get("source")
                    or chunk.get("source", "로컬 문서")
                ),
                "source_url": cls._public_url(metadata.get("source_url", "")),
                "published_at": str(metadata.get("published_at", "")),
                "document_id": str(metadata.get("document_id", "")),
                "chunk_id": str(chunk.get("chunk_id", metadata.get("chunk_id", ""))),
                "content": str(chunk.get("text", "")),
            })

        for index, document in enumerate(
            web_documents[: cls.MAX_WEB_DOCUMENTS],
            1,
        ):
            entries.append({
                "source_id": f"WEB-{index:03d}",
                "source_type": str(document.get("search_focus", "web")),
                "title": str(document.get("title", "웹 자료")),
                "source_url": cls._public_url(document.get("url", "")),
                "published_at": str(document.get("published_date", "")),
                "document_id": "",
                "chunk_id": "",
                "content": str(document.get("content", "")),
            })
        return entries

    @classmethod
    def resolve(
        cls,
        debate: dict[str, Any],
        catalog: list[dict[str, Any]],
    ) -> dict[str, Any]:
        resolved = deepcopy(debate)
        by_id = {str(entry.get("source_id", "")): entry for entry in catalog}
        evidence_number = 0

        for round_data in resolved.get("rounds", []):
            for side in ("bull_response", "bear_response"):
                response = round_data.get(side, {})
                for issue in response.get("issues", []):
                    evidence_items = issue.get("evidence", [])
                    if not isinstance(evidence_items, list):
                        continue
                    enriched = []
                    for item in evidence_items:
                        if not isinstance(item, dict):
                            enriched.append(item)
                            continue
                        evidence_number += 1
                        enriched.append(
                            cls._resolve_item(
                                item,
                                by_id,
                                f"E-{evidence_number:03d}",
                            )
                        )
                    issue["evidence"] = enriched

        resolved["evidence_catalog"] = catalog
        return resolved

    @classmethod
    def _resolve_item(
        cls,
        item: dict[str, Any],
        by_id: dict[str, dict[str, Any]],
        evidence_id: str,
    ) -> dict[str, Any]:
        source_id = str(item.get("source_id", ""))
        quote = str(item.get("exact_quote", "")).strip()
        source = by_id.get(source_id)
        context = cls._paragraph_for_quote(
            str(source.get("content", "")) if source else "",
            quote,
        )
        return {
            "evidence_id": evidence_id,
            "source_id": source_id,
            "exact_quote": quote,
            "reason": str(item.get("reason", "")),
            "verified": bool(source and context),
            "context_text": context,
            "title": str(source.get("title", "")) if source else "",
            "source_type": str(source.get("source_type", "")) if source else "",
            "source_url": str(source.get("source_url", "")) if source else "",
            "published_at": str(source.get("published_at", "")) if source else "",
            "document_id": str(source.get("document_id", "")) if source else "",
            "chunk_id": str(source.get("chunk_id", "")) if source else "",
        }

    @staticmethod
    def _paragraph_for_quote(content: str, quote: str) -> str:
        if not content or not quote:
            return ""
        start = content.casefold().find(quote.casefold())
        if start < 0:
            return ""
        paragraph_start = content.rfind("\n\n", 0, start)
        paragraph_end = content.find("\n\n", start + len(quote))
        paragraph_start = 0 if paragraph_start < 0 else paragraph_start + 2
        paragraph_end = len(content) if paragraph_end < 0 else paragraph_end
        return content[paragraph_start:paragraph_end].strip()

    @staticmethod
    def _financial_entry(financial_data: dict[str, Any]) -> dict[str, Any]:
        ticker = str(financial_data.get("ticker", "")).strip()
        url = f"https://finance.yahoo.com/quote/{ticker}" if ticker else ""
        return {
            "source_id": "FIN-001",
            "source_type": "financial_data",
            "title": f"{ticker or '기업'} 금융 데이터",
            "source_url": url,
            "published_at": str(financial_data.get("price_date", "")),
            "document_id": "",
            "chunk_id": "",
            "content": json.dumps(
                financial_data,
                ensure_ascii=False,
                indent=2,
                default=str,
            ),
        }

    @staticmethod
    def _public_url(value: Any) -> str:
        url = str(value or "").strip()
        try:
            parts = urlsplit(url)
        except ValueError:
            return ""
        return url if parts.scheme in {"http", "https"} and parts.netloc else ""
