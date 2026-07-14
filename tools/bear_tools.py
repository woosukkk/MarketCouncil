from rag.retriever import ReportRetriever
from tools.financial_data import get_financial_data


class BearTools:
    def __init__(self) -> None:
        self.retriever = ReportRetriever()

    def get_company_financials(self, company_name: str) -> dict:
        return get_financial_data(company_name)

    def search_company_reports(
        self,
        company_name: str,
        top_k: int = 3,
    ) -> list[dict]:
        query = (
            f"{company_name}의 위험 요인, 실적 악화 가능성, "
            "부정적인 투자 근거와 하락 요인"
        )

        return self.retriever.search(
            query=query,
            top_k=top_k,
        )