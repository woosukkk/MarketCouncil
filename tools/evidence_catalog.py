import json
import math
import re
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from typing import Any
from tools.evidence_dates import parse_evidence_date
from tools.evidence_text import is_navigation_text
from urllib.parse import urlsplit


class EvidenceCatalog:
    MAX_WEB_DOCUMENTS = 16
    MAX_QUOTES_PER_SOURCE = 16

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
            entry = {
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
                "page_number": metadata.get("page_number"),
                "content": str(chunk.get("text", "")),
            }
            entries.append(cls._with_quotes(entry))

        for index, document in enumerate(
            web_documents[: cls.MAX_WEB_DOCUMENTS],
            1,
        ):
            entry = {
                "source_id": f"WEB-{index:03d}",
                "source_type": str(document.get("search_focus", "web")),
                "title": str(document.get("title", "웹 자료")),
                "source_url": cls._public_url(document.get("url", "")),
                "published_at": str(document.get("published_date", "")),
                "document_id": "",
                "chunk_id": "",
                "page_number": None,
                "content": str(document.get("content", "")),
                "extraction_method": str(document.get("extraction_method", "")),
                "body_extraction_status": str(document.get("body_extraction_status", "")),
            }
            entries.append(cls._with_quotes(entry))
        return entries

    @classmethod
    def from_web_documents(
        cls,
        documents: list[dict[str, Any]],
        prefix: str = "HIST",
    ) -> list[dict[str, Any]]:
        return [
            cls._with_quotes({
                "source_id": f"{prefix}-{index:03d}",
                "source_type": str(document.get("search_focus", "web")),
                "title": str(document.get("title", "역사 자료")),
                "source_url": cls._public_url(document.get("url", "")),
                "published_at": str(document.get("published_date", "")),
                "document_id": "",
                "chunk_id": "",
                "page_number": None,
                "content": str(document.get("content", "")),
                "extraction_method": str(document.get("extraction_method", "")),
                "body_extraction_status": str(document.get("body_extraction_status", "")),
            })
            for index, document in enumerate(documents, 1)
        ]

    @staticmethod
    def for_prompt(catalog: list[dict[str, Any]]) -> list[dict[str, Any]]:
        fields = (
            "source_id",
            "source_type",
            "title",
            "published_at",
            "extraction_method",
            "body_extraction_status",
            "quotes",
        )
        return [{key: entry.get(key) for key in fields} for entry in catalog]

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
        source = by_id.get(source_id)
        quote_id = str(item.get("quote_id", "")).strip()
        quote_entry = next(
            (
                quote for quote in (source or {}).get("quotes", [])
                if str(quote.get("quote_id", "")) == quote_id
            ),
            {},
        )
        quote = str(
            quote_entry.get("text") or item.get("exact_quote", "")
        ).strip()
        context = cls._paragraph_for_quote(
            str(source.get("content", "")) if source else "",
            quote,
        )
        return {
            "evidence_id": evidence_id,
            "source_id": source_id,
            "quote_id": quote_id,
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
            "page_number": source.get("page_number") if source else None,
            "source_page_url": cls._page_url(
                str(source.get("source_url", "")) if source else "",
                source.get("page_number") if source else None,
            ),
        }

    @classmethod
    def resolve_quote(
        cls,
        item: dict[str, Any],
        catalog: list[dict[str, Any]],
        evidence_id: str,
    ) -> dict[str, Any]:
        by_id = {str(entry.get("source_id", "")): entry for entry in catalog}
        return cls._resolve_item(item, by_id, evidence_id)

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
        facts = financial_data.get("financial_facts") or {}
        metrics = financial_data.get("derived_metrics") or {}
        history = [row for row in facts.get("annual_history", [])[:5] if isinstance(row, dict)]
        currency = facts.get("financial_currency") or financial_data.get("financial_currency") or "재무 통화 단위 미제공"
        price_currency = facts.get("price_currency") or financial_data.get("price_currency") or "주가 통화 단위 미제공"
        period_text = ", ".join(str(row.get("period") or "기간 미제공") for row in history) or "재무 기준기간 미제공"
        current_period = str(history[0].get("period") or "기간 미제공") if history else "기간 미제공"
        previous_period = str(history[1].get("period") or "기간 미제공") if len(history) > 1 else "기간 미제공"
        price_date = parse_evidence_date(financial_data.get("price_date") or facts.get("price_date"))
        price_day = price_date.isoformat() if price_date else "기준일 미제공"

        def amount(value: Any, unit: str = currency) -> str:
            if value is None:
                return "확인 불가"
            try:
                number = Decimal(str(value).replace(",", ""))
            except InvalidOperation:
                return "확인 불가"
            if not number.is_finite():
                return "확인 불가"
            converted = f" (조원 환산={(number / Decimal('1e12')).normalize():f}조원)" if unit == "KRW" and abs(number) >= Decimal('1e12') else ""
            return f"{value} {unit}{converted}"

        def ratio(value: Any) -> str:
            if type(value) in (int, float) and math.isfinite(value):
                return f"{value * 100:.12g}% (원래 비율 {value})"
            return "확인 불가"

        candidates = [
            f"주가 기준일={price_day}; 현재 주가={amount(facts.get('current_price', financial_data.get('current_price')), price_currency)}; 시가총액={amount(facts.get('market_cap'), price_currency)}; 주가일은 재무 기준기간이 아님.",
            f"매출 비교: 현재 연간({current_period})={amount(financial_data.get('current_revenue'))}; 이전 연간({previous_period})={amount(financial_data.get('previous_revenue'))}; 제공된 성장률={financial_data.get('revenue_growth', '확인 불가')}; 재무 기준기간={period_text}.",
            f"영업이익 비교: 현재 연간({current_period})={amount(financial_data.get('current_operating_income'))}; 이전 연간({previous_period})={amount(financial_data.get('previous_operating_income'))}; 제공된 변화={financial_data.get('operating_income_growth', '확인 불가')}; 재무 기준기간={period_text}.",
        ]
        if metrics:
            fcf_rows = [{"period": row.get("period"), "free_cash_flow": amount(row.get("free_cash_flow"))} for row in history]
            candidates.extend([
                f"정규화 FCF(normalized_fcf)={amount(metrics.get('normalized_fcf'))}; 구분=제공된 계산 지표; 기준=사용 가능한 최근 최대 5개 연간 FCF의 평균; 연간 입력={json.dumps(fcf_rows, ensure_ascii=False, default=str)}.",
                f"FCF yield(fcf_yield)={ratio(metrics.get('fcf_yield'))}; 구분=제공된 계산 지표; 기준=정규화 연간 FCF/시가총액; FCF={amount(metrics.get('normalized_fcf'))}; 시가총액={amount(facts.get('market_cap'), price_currency)}; 주가 기준일={price_day}; 재무 기준기간={period_text}.",
                f"발행 주식 수 변화율(dilution_rate)={ratio(metrics.get('dilution_rate'))}; 구분=제공된 계산 지표, EPS 희석률 아님; 기준=유효한 최신/최초 연간 발행 주식 수의 비율에서 1 차감; 입력={json.dumps([{'period': row.get('period'), 'shares_outstanding': str(row['shares_outstanding']) + ' 주' if row.get('shares_outstanding') is not None else '확인 불가'} for row in history], ensure_ascii=False, default=str)}.",
            ])
            for key, label in [("average_cash_conversion", "FCF/순이익 평균"), ("debt_to_equity", "최근 총부채/자본"), ("positive_fcf_ratio", "양의 연간 FCF 비율"), ("revenue_growth_volatility", "연간 매출 증가율 표준편차"), ("operating_margin_volatility", "연간 영업이익률 표준편차")]:
                metric_period = current_period if key == "debt_to_equity" else period_text
                candidates.append(f"{label}({key})={ratio(metrics.get(key))}; 구분=제공된 계산 지표; 재무 기준기간={metric_period}.")
            candidates.append(f"계산 한계: 누락 입력={json.dumps(metrics.get('missing_inputs', []), ensure_ascii=False)}; 제공된 가정={json.dumps(metrics.get('assumptions', []), ensure_ascii=False)}; 기간별 통화 변동·환산 여부는 입력에 없으면 확인 불가; 단기 추세나 미래 실적을 확정하지 않음.")
        if history:
            candidates.append(f"최근 연간 원본 입력(주가 기준일과 별개): {json.dumps(history[0], ensure_ascii=False, default=str)}; 통화={currency}.")
        candidates = candidates[:EvidenceCatalog.MAX_QUOTES_PER_SOURCE]
        return {
            "source_id": "FIN-001", "source_type": "financial_data",
            "title": f"{ticker or '기업'} 금융 데이터",
            "source_url": f"https://finance.yahoo.com/quote/{ticker}" if ticker else "",
            "published_at": price_date.isoformat() if price_date else "",
            "document_id": "", "chunk_id": "", "page_number": None,
            "content": "\n\n".join(candidates),
            "quotes": [{"quote_id": f"FIN-001-Q{index:02d}", "text": text} for index, text in enumerate(candidates, 1)],
        }

    @classmethod
    def _with_quotes(cls, entry: dict[str, Any]) -> dict[str, Any]:
        published = parse_evidence_date(entry.get("published_at"))
        entry["published_at"] = published.isoformat() if published else ""
        source_id = str(entry.get("source_id", ""))
        content = str(entry.get("content", ""))
        candidates: list[str] = []
        seen: set[str] = set()

        def append(start: int | None, end: int) -> None:
            if start is None:
                return
            text = content[start:end].strip()
            if len(text) >= 15 and text.casefold() not in seen and not is_navigation_text(text):
                candidates.append(text)
                seen.add(text.casefold())

        start: int | None = None
        end = 0
        # Keep adjacent table labels and short numeric rows together, using exact source spans.
        for match in re.finditer(r"[^\r\n]+", content):
            line = match.group()
            if is_navigation_text(line):
                append(start, end)
                start = None
                continue
            if start is not None and match.end() - start > 500:
                append(start, end)
                start = None
            position = match.start()
            while match.end() - position > 500:
                boundary = content.rfind(" ", position, position + 501)
                boundary = boundary if boundary > position else position + 500
                append(position, boundary)
                position = boundary
                while position < match.end() and content[position].isspace():
                    position += 1
            start = position if start is None else start
            end = match.end()
        append(start, end)
        entry["quotes"] = [
            {"quote_id": f"{source_id}-Q{index:02d}", "text": text}
            for index, text in enumerate(candidates[: cls.MAX_QUOTES_PER_SOURCE], 1)
        ]
        return entry

    @staticmethod
    def _page_url(url: str, page_number: Any) -> str:
        if not url or not page_number:
            return url
        separator = "&" if "#" in url else "#"
        return f"{url}{separator}page={page_number}"

    @staticmethod
    def _public_url(value: Any) -> str:
        url = str(value or "").strip()
        try:
            parts = urlsplit(url)
        except ValueError:
            return ""
        return url if parts.scheme in {"http", "https"} and parts.netloc else ""
