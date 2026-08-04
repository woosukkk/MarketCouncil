from datetime import date

from rag.retriever import ReportRetriever
from tools.financial_data import get_financial_data
from tools.web_search_tool import WebSearchTool


class BullTools:
    def __init__(self, retriever: ReportRetriever | None = None) -> None:
        self.retriever = retriever or ReportRetriever()
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
            as_of_date=date.today().isoformat(),
        )

    def search_regulatory_filings(
        self,
        company_name: str,
        top_k: int = 8,
    ) -> list[dict]:
        query = (
            f"{company_name} 공식 공시 재무 실적 계약 위험 요인 "
            "자본 조달 사업 변화"
        )
        return self.retriever.search(
            query=query,
            top_k=top_k,
            as_of_date=date.today().isoformat(),
            source_types={"regulatory_filing"},
        )

    def search_recent_web(
        self,
        company_name: str,
    ) -> str:
        return self.web_search.search_recent_bull_evidence(
            company_name
        )
