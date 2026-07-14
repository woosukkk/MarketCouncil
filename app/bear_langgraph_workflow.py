from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from tools.bear_tools import BearTools


class BearState(TypedDict, total=False):
    company_name: str
    financial_data: dict
    retrieved_chunks: list[dict]
    report_context: str


class BearGraphWorkflow:
    def __init__(self) -> None:
        self.tools = BearTools()
        self.graph = self._build_graph()

    def collect_financial_data(
        self,
        state: BearState,
    ) -> BearState:
        financial_data = self.tools.get_company_financials(
            state["company_name"]
        )

        return {
            "financial_data": financial_data,
        }

    def retrieve_reports(
        self,
        state: BearState,
    ) -> BearState:
        retrieved_chunks = self.tools.search_company_reports(
            state["company_name"],
            top_k=3,
        )

        return {
            "retrieved_chunks": retrieved_chunks,
        }

    def build_report_context(
        self,
        state: BearState,
    ) -> BearState:
        report_context = "\n\n".join(
            f"""출처: {chunk["source"]}
청크 번호: {chunk["chunk_id"]}
내용:
{chunk["text"]}"""
            for chunk in state["retrieved_chunks"]
        )

        return {
            "report_context": report_context,
        }

    def _build_graph(self):
        builder = StateGraph(BearState)

        builder.add_node(
            "collect_financial_data",
            self.collect_financial_data,
        )
        builder.add_node(
            "retrieve_reports",
            self.retrieve_reports,
        )
        builder.add_node(
            "build_report_context",
            self.build_report_context,
        )

        builder.add_edge(START, "collect_financial_data")
        builder.add_edge(
            "collect_financial_data",
            "retrieve_reports",
        )
        builder.add_edge(
            "retrieve_reports",
            "build_report_context",
        )
        builder.add_edge("build_report_context", END)

        return builder.compile()

    def run(self, company_name: str) -> BearState:
        return self.graph.invoke({
            "company_name": company_name,
        })