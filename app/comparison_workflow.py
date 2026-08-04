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
    shared_report_context: str

    bull_web_context: str
    bear_web_context: str
    shared_web_context: str
    source_data: dict
    evidence_bundle: dict


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
            "shared_report_context": self._build_context(
                self._deduplicate_chunks(
                    state.get("bull_chunks", [])
                    + state.get("bear_chunks", [])
                )
            ),
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

        shared_web_context = self._build_web_context(articles)

        return {
            "bull_web_context": shared_web_context,
            "bear_web_context": shared_web_context,
            "shared_web_context": shared_web_context,
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

    @staticmethod
    def _build_context(
        chunks: list[dict],
    ) -> str:
        if not chunks:
            return "검색된 로컬 리포트 없음"

        return "\n\n".join(
            f"""출처: {chunk.get("source", "알 수 없음")}
청크 번호: {chunk.get("chunk_id", "알 수 없음")}
내용:
{chunk.get("text", "")}"""
            for chunk in chunks
        )

    @staticmethod
    def _build_web_context(
        articles: list[dict],
        sentiment: str | None = None,
    ) -> str:
        selected = [
            article
            for article in articles
            if isinstance(article, dict)
            and (
                sentiment is None
                or article.get("sentiment") == sentiment
            )
            and article.get("use_as_evidence", True)
        ]

        if not selected:
            return "사용 가능한 최신 웹 근거 없음"

        return "\n\n".join(
            f"""제목: {article.get("title", "알 수 없음")}
내용: {article.get("reason", "")}
자료 유형: {article.get("source_type", "알 수 없음")}
출처: {article.get("source", "알 수 없음")}
게시일: {article.get("published_date", "알 수 없음")}
신뢰도: {article.get("credibility_score", 0.0)}
URL: {article.get("url", "")}"""
            for article in selected
        )

    @staticmethod
    def _deduplicate_chunks(chunks: list[dict]) -> list[dict]:
        unique_chunks: list[dict] = []
        seen: set[tuple[str, str]] = set()

        for chunk in chunks:
            key = (
                str(chunk.get("source", "")),
                str(chunk.get("chunk_id", "")),
            )
            if key in seen:
                continue
            seen.add(key)
            unique_chunks.append(chunk)

        return unique_chunks

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
            "build_report_contexts",
        )
        builder.add_edge(
            "build_report_contexts",
            "collect_web_sources",
        )
        builder.add_edge(
            "collect_web_sources",
            "resolve_evidence",
        )
        builder.add_edge(
            "resolve_evidence",
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
