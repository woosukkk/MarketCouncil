from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from tools.bull_tools import BullTools
from tools.bear_tools import BearTools
from tools.evidence_resolver import EvidenceResolver
from tools.source_collector import SourceCollector


class ComparisonState(TypedDict, total=False):
    company_name: str
    financial_data: dict

    bull_chunks: list[dict]
    bear_chunks: list[dict]

    bull_report_context: str
    bear_report_context: str

    bull_web_context: str
    bear_web_context: str
    source_data: dict
    evidence_bundle: dict
    evidence_catalog: list[dict]


class ComparisonWorkflow:
    def __init__(self) -> None:
        self.bull_tools = BullTools()
        self.bear_tools = BearTools()
        self.source_collector = SourceCollector()
        self.evidence_resolver = EvidenceResolver()
        self.graph = self._build_graph()

    def collect_financial_data(
        self,
        state: ComparisonState,
    ) -> ComparisonState:
        print("[1] 공통 금융 데이터 수집 시작")

        financial_data = (
            self.bull_tools.get_company_financials(
                state["company_name"]
            )
        )

        print("[1] 공통 금융 데이터 수집 완료")

        return {
            "financial_data": financial_data,
        }

    def retrieve_bull_reports(
        self,
        state: ComparisonState,
    ) -> ComparisonState:
        print("[2] Bull 로컬 리포트 검색 시작")

        bull_chunks = (
            self.bull_tools.search_company_reports(
                state["company_name"],
                top_k=3,
            )
        )

        print("[2] Bull 로컬 리포트 검색 완료")

        return {
            "bull_chunks": bull_chunks,
        }

    def retrieve_bear_reports(
        self,
        state: ComparisonState,
    ) -> ComparisonState:
        print("[3] Bear 로컬 리포트 검색 시작")

        bear_chunks = (
            self.bear_tools.search_company_reports(
                state["company_name"],
                top_k=3,
            )
        )

        print("[3] Bear 로컬 리포트 검색 완료")

        return {
            "bear_chunks": bear_chunks,
        }

    def build_report_contexts(
        self,
        state: ComparisonState,
    ) -> ComparisonState:
        bull_report_context = self._build_context(
            state.get("bull_chunks", [])
        )

        bear_report_context = self._build_context(
            state.get("bear_chunks", [])
        )

        return {
            "bull_report_context": bull_report_context,
            "bear_report_context": bear_report_context,
        }

    def collect_web_sources(
        self,
        state: ComparisonState,
    ) -> ComparisonState:
        print("[4] 통합 최신 뉴스 수집 시작")

        source_data = self.source_collector.collect(
            state["company_name"],
            ticker=state.get("financial_data", {}).get("ticker"),
        )

        print("[4] 통합 최신 뉴스 수집 완료")

        return {
            "source_data": source_data,
        }

    def build_web_contexts(
        self,
        state: ComparisonState,
    ) -> ComparisonState:
        articles = state.get("source_data", {}).get(
            "articles",
            [],
        )

        return {
            "bull_web_context": self._build_web_context(
                articles,
                "positive",
            ),
            "bear_web_context": self._build_web_context(
                articles,
                "negative",
            ),
        }

    def resolve_evidence(
        self,
        state: ComparisonState,
    ) -> ComparisonState:
        print("[5] 웹/RAG 중복 근거 확인 시작")

        source_data = self.evidence_resolver.resolve(
            state.get("source_data", {})
        )

        print("[5] 웹/RAG 중복 근거 확인 완료")

        return {
            "source_data": source_data,
            "evidence_bundle": source_data.get(
                "evidence_bundle",
                {},
            ),
        }

    def build_evidence_catalog(
        self,
        state: ComparisonState,
    ) -> ComparisonState:
        catalog: list[dict] = []
        for key, value in state.get("financial_data", {}).items():
            catalog.append({
                "id": f"financial.{key}",
                "type": "financial",
                "value": value,
                "available": value not in {None, "", "데이터 없음"},
            })
        for perspective in ("bull", "bear"):
            for index, chunk in enumerate(state.get(f"{perspective}_chunks", []), 1):
                evidence_id = f"rag.{perspective}.{chunk.get('chunk_id', index)}"
                chunk["evidence_id"] = evidence_id
                catalog.append({
                    "id": evidence_id,
                    "type": "rag",
                    "source": chunk.get("source", ""),
                    "available": bool(chunk.get("text")),
                })
        source_data = state.get("source_data", {})
        for index, article in enumerate(source_data.get("articles", []), 1):
            event_key = str(article.get("event_key", "")).strip()
            evidence_id = f"web.{index}.{event_key or 'event'}"
            article["evidence_id"] = evidence_id
            catalog.append({
                "id": evidence_id,
                "type": "web",
                "source": article.get("source", ""),
                "url": article.get("url", ""),
                "available": bool(article.get("reason") or article.get("title")),
            })
        return {"source_data": source_data, "evidence_catalog": catalog}

    @staticmethod
    def _build_context(
        chunks: list[dict],
    ) -> str:
        if not chunks:
            return "검색된 로컬 리포트 없음"

        return "\n\n".join(
            f"""출처: {chunk.get("source", "알 수 없음")}
근거 ID: {chunk.get("evidence_id", "")}
청크 번호: {chunk.get("chunk_id", "알 수 없음")}
내용:
{chunk.get("text", "")}"""
            for chunk in chunks
        )

    @staticmethod
    def _build_web_context(
        articles: list[dict],
        sentiment: str,
    ) -> str:
        selected = [
            article
            for article in articles
            if isinstance(article, dict)
            and article.get("sentiment") == sentiment
            and article.get("use_as_evidence", True)
        ]

        if not selected:
            return "해당 방향의 최신 웹 근거 없음"

        return "\n\n".join(
            f"""제목: {article.get("title", "알 수 없음")}
근거 ID: {article.get("evidence_id", "")}
내용: {article.get("reason", "")}
자료 유형: {article.get("source_type", "알 수 없음")}
출처: {article.get("source", "알 수 없음")}
게시일: {article.get("published_date", "알 수 없음")}
신뢰도: {article.get("credibility_score", 0.0)}
URL: {article.get("url", "")}"""
            for article in selected
        )

    def _build_graph(self):
        builder = StateGraph(ComparisonState)

        builder.add_node(
            "collect_financial_data",
            self.collect_financial_data,
        )
        builder.add_node(
            "retrieve_bull_reports",
            self.retrieve_bull_reports,
        )
        builder.add_node(
            "retrieve_bear_reports",
            self.retrieve_bear_reports,
        )
        builder.add_node(
            "build_report_contexts",
            self.build_report_contexts,
        )
        builder.add_node(
            "collect_web_sources",
            self.collect_web_sources,
        )
        builder.add_node(
            "resolve_evidence",
            self.resolve_evidence,
        )
        builder.add_node(
            "build_web_contexts",
            self.build_web_contexts,
        )
        builder.add_node(
            "build_evidence_catalog",
            self.build_evidence_catalog,
        )

        builder.add_edge(
            START,
            "collect_financial_data",
        )
        builder.add_edge(
            "collect_financial_data",
            "retrieve_bull_reports",
        )
        builder.add_edge(
            "retrieve_bull_reports",
            "retrieve_bear_reports",
        )
        builder.add_edge(
            "retrieve_bear_reports",
            "collect_web_sources",
        )
        builder.add_edge(
            "collect_web_sources",
            "resolve_evidence",
        )
        builder.add_edge(
            "resolve_evidence",
            "build_evidence_catalog",
        )
        builder.add_edge(
            "build_evidence_catalog",
            "build_report_contexts",
        )
        builder.add_edge(
            "build_report_contexts",
            "build_web_contexts",
        )
        builder.add_edge(
            "build_web_contexts",
            END,
        )

        return builder.compile()

    def run(
        self,
        company_name: str,
    ) -> ComparisonState:
        return self.graph.invoke({
            "company_name": company_name,
        })
