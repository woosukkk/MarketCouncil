from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from tools.bull_tools import BullTools
from tools.bear_tools import BearTools


class ComparisonState(TypedDict, total=False):
    company_name: str
    financial_data: dict

    bull_chunks: list[dict]
    bear_chunks: list[dict]

    bull_report_context: str
    bear_report_context: str

    bull_web_context: str
    bear_web_context: str


class ComparisonWorkflow:
    def __init__(self) -> None:
        self.bull_tools = BullTools()
        self.bear_tools = BearTools()
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

    def search_bull_web(
        self,
        state: ComparisonState,
    ) -> ComparisonState:
        print("[4] Bull 최신 웹 근거 조회 시작")

        bull_web_context = (
            self.bull_tools.search_recent_web(
                state["company_name"]
            )
        )

        print("[4] Bull 최신 웹 근거 조회 완료")

        return {
            "bull_web_context": bull_web_context,
        }

    def search_bear_web(
        self,
        state: ComparisonState,
    ) -> ComparisonState:
        print("[5] Bear 최신 웹 근거 조회 시작")

        bear_web_context = (
            self.bear_tools.search_recent_web(
                state["company_name"]
            )
        )

        print("[5] Bear 최신 웹 근거 조회 완료")

        return {
            "bear_web_context": bear_web_context,
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
            "search_bull_web",
            self.search_bull_web,
        )
        builder.add_node(
            "search_bear_web",
            self.search_bear_web,
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
            "search_bull_web",
        )
        builder.add_edge(
            "search_bull_web",
            "search_bear_web",
        )
        builder.add_edge(
            "search_bear_web",
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