from rag.retriever import ReportRetriever
from tools.financial_data import get_financial_data
from tools.web_search_tool import WebSearchTool


class BullTools:
    def __init__(self) -> None:
        self.retriever = ReportRetriever()
        self.web_search = WebSearchTool()

    def get_company_financials(
        self,
        company_name: str,
    ) -> dict:
        return get_financial_data(company_name)

    def search_company_reports(
        self,
        company_name: str,
        top_k: int = 3,
    ) -> list[dict]:
        query = (
            f"{company_name}의 긍정적인 성장 요인과 "
            "투자 근거, 기술 경쟁력, 실적 성장"
        )

        return self.retriever.search(
            query=query,
            top_k=top_k,
        )

    def search_recent_web(
        self,
        company_name: str,
    ) -> str:
        return self.web_search.search_recent_bull_evidence(
            company_name
        )