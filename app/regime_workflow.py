from datetime import date
from typing import Any, Callable

from agents.regime_reason_agent import RegimeReasonAgent
from tools.evidence_catalog import EvidenceCatalog
from tools.market_regime import detect_regimes, fetch_price_history


HistoryProvider = Callable[[str], list[dict[str, Any]]]


class RegimeWorkflow:
    def __init__(
        self,
        reason_agent: RegimeReasonAgent | None = None,
        history_provider: HistoryProvider = fetch_price_history,
    ) -> None:
        self.reason_agent = reason_agent or RegimeReasonAgent()
        self.history_provider = history_provider

    def run(
        self,
        company_name: str,
        ticker: str,
        evidence_catalog: list[dict[str, Any]],
    ) -> dict[str, Any]:
        prices = self.history_provider(ticker)
        benchmark_ticker = self._benchmark_ticker(ticker)
        benchmark_error = ""
        try:
            benchmark_prices = self.history_provider(benchmark_ticker)
        except RuntimeError as error:
            benchmark_prices = []
            benchmark_error = str(error)
        analysis = detect_regimes(
            company_name,
            ticker,
            prices,
            benchmark_prices=benchmark_prices,
            benchmark_ticker=benchmark_ticker,
        )
        analysis["timeline_evidence"] = self._timeline_evidence(
            analysis.get("display_series", {}),
            evidence_catalog,
            analysis.get("price_series", []),
            analysis.get("benchmark_series", []),
        )
        if benchmark_error:
            analysis["limitations"].append(
                f"벤치마크 비교를 수행하지 못했습니다: {benchmark_error}"
            )
        if not analysis.get("regimes"):
            return analysis

        candidates = self._candidates(analysis, evidence_catalog)
        if not any(candidates.values()):
            analysis["limitations"].append(
                "비교 기간 안에 발표일과 원문이 확인되는 자료가 없어 이유를 생성하지 않았습니다."
            )
            return analysis
        try:
            raw_reasons = self.reason_agent.analyze({
                "regimes": analysis["regimes"],
                "evidence_by_regime": candidates,
            })
        except RuntimeError as error:
            analysis["limitations"].append(str(error))
            return analysis

        analysis["reasons"] = self._resolve_reasons(
            raw_reasons,
            evidence_catalog,
            analysis["price_series"],
            analysis.get("benchmark_series", []),
            {
                regime_id: {str(item.get("source_id", "")) for item in items}
                for regime_id, items in candidates.items()
            },
        )
        return analysis

    @staticmethod
    def _timeline_evidence(
        display_series: dict[str, list[dict[str, Any]]],
        catalog: list[dict[str, Any]],
        prices: list[dict[str, Any]],
        benchmark_prices: list[dict[str, Any]],
    ) -> dict[str, dict[str, list[dict[str, Any]]]]:
        limits = {"recent_daily": 2, "medium_monthly": 3, "historical_quarterly": 5}
        timeline: dict[str, dict[str, list[dict[str, Any]]]] = {}
        for group, rows in display_series.items():
            timeline[group] = {}
            for row in rows:
                period = str(row.get("period", ""))
                matched = []
                for source in catalog:
                    published = RegimeWorkflow._date(source.get("published_at"))
                    if published is None or not (
                        str(row.get("start_date", ""))
                        <= published.isoformat()
                        <= str(row.get("end_date", ""))
                    ):
                        continue
                    quote = next(iter(source.get("quotes", [])), {})
                    if not quote:
                        continue
                    source_id = str(source.get("source_id", ""))
                    evidence = EvidenceCatalog.resolve_quote(
                        {
                            "source_id": source_id,
                            "quote_id": quote.get("quote_id", ""),
                            "reason": "해당 기간에 게시된 자료",
                        },
                        catalog,
                        f"TE-{source_id}",
                    )
                    evidence.update(RegimeWorkflow._price_reaction(
                        evidence,
                        prices,
                        benchmark_prices,
                    ))
                    matched.append(evidence)
                timeline[group][period] = matched[: limits.get(group, 3)]
        return timeline

    @staticmethod
    def _candidates(
        analysis: dict[str, Any],
        catalog: list[dict[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        selected: dict[str, list[dict[str, Any]]] = {}
        for regime_id, regime in analysis["regimes"].items():
            start = date.fromisoformat(regime["start_date"])
            end = date.fromisoformat(regime["end_date"])
            items = []
            for source in catalog:
                published = RegimeWorkflow._date(source.get("published_at"))
                content = str(source.get("content", "")).strip()
                if published is None or not start <= published <= end or not content:
                    continue
                items.append({
                    "source_id": source.get("source_id", ""),
                    "title": source.get("title", ""),
                    "published_at": str(published),
                    "source_type": source.get("source_type", ""),
                    "quotes": source.get("quotes", []),
                })
            selected[regime_id] = items[:20]
        return selected

    @staticmethod
    def _resolve_reasons(
        raw: dict[str, Any],
        catalog: list[dict[str, Any]],
        prices: list[dict[str, Any]],
        benchmark_prices: list[dict[str, Any]],
        allowed_sources: dict[str, set[str]],
    ) -> dict[str, list[dict[str, Any]]]:
        resolved: dict[str, list[dict[str, Any]]] = {
            "past_bull": [],
            "recent_bear": [],
        }
        evidence_number = 0
        for regime_id in resolved:
            for reason_number, reason in enumerate(raw.get(regime_id, [])[:2], 1):
                evidence_items = []
                for item in reason.get("evidence", [])[:2]:
                    evidence_number += 1
                    evidence = EvidenceCatalog.resolve_quote(
                        item,
                        catalog,
                        f"RE-{evidence_number:03d}",
                    )
                    if str(item.get("source_id", "")) not in allowed_sources.get(regime_id, set()):
                        evidence["verified"] = False
                        evidence["context_text"] = ""
                    evidence.update(
                        RegimeWorkflow._price_reaction(
                            evidence,
                            prices,
                            benchmark_prices,
                        )
                    )
                    evidence_items.append(evidence)
                resolved[regime_id].append({
                    "reason_id": f"{regime_id.upper()}-{reason_number:02d}",
                    "claim": str(reason.get("claim", "")),
                    "classification": str(reason.get("classification", "ANALYST_HYPOTHESIS")),
                    "explanation": str(reason.get("explanation", "")),
                    "verified": bool(evidence_items) and all(
                        item.get("verified") for item in evidence_items
                    ),
                    "evidence": evidence_items,
                })
        return resolved

    @staticmethod
    def _price_reaction(
        evidence: dict[str, Any],
        prices: list[dict[str, Any]],
        benchmark_prices: list[dict[str, Any]],
    ) -> dict[str, Any]:
        event_date = RegimeWorkflow._date(evidence.get("published_at"))
        if event_date is None:
            return {"event_date": "", "price_reaction_1d_pct": None, "price_reaction_5d_pct": None}
        ordered = sorted(prices, key=lambda item: str(item.get("date", "")))
        index = next(
            (
                position for position, item in enumerate(ordered)
                if RegimeWorkflow._date(item.get("date"))
                and RegimeWorkflow._date(item.get("date")) >= event_date
            ),
            None,
        )
        if index is None:
            return {"event_date": str(event_date), "price_reaction_1d_pct": None, "price_reaction_5d_pct": None}
        base = float(ordered[index]["close"])

        def reaction(offset: int) -> float | None:
            target = index + offset
            if target >= len(ordered) or base == 0:
                return None
            return round((float(ordered[target]["close"]) / base - 1) * 100, 2)

        result = {
            "event_date": str(event_date),
            "price_reaction_1d_pct": reaction(1),
            "price_reaction_5d_pct": reaction(5),
        }
        benchmark_5d = RegimeWorkflow._reaction(benchmark_prices, event_date, 5)
        result["market_adjusted_5d_pct"] = (
            round(result["price_reaction_5d_pct"] - benchmark_5d, 2)
            if result["price_reaction_5d_pct"] is not None and benchmark_5d is not None
            else None
        )
        return result

    @staticmethod
    def _reaction(
        prices: list[dict[str, Any]],
        event_date: date,
        offset: int,
    ) -> float | None:
        ordered = sorted(prices, key=lambda item: str(item.get("date", "")))
        index = next(
            (
                position for position, item in enumerate(ordered)
                if RegimeWorkflow._date(item.get("date"))
                and RegimeWorkflow._date(item.get("date")) >= event_date
            ),
            None,
        )
        if index is None or index + offset >= len(ordered):
            return None
        base = float(ordered[index]["close"])
        if base == 0:
            return None
        return round((float(ordered[index + offset]["close"]) / base - 1) * 100, 2)

    @staticmethod
    def _benchmark_ticker(ticker: str) -> str:
        if ticker.endswith(".KS"):
            return "^KS11"
        if ticker.endswith(".KQ"):
            return "^KQ11"
        return "^GSPC"

    @staticmethod
    def _date(value: Any) -> date | None:
        text = str(value or "").strip()[:10]
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None
