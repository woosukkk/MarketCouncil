from financial_data import get_financial_data
from retriever import ReportRetriever


class BullTools:
    def __init__(self) -> None:
        self.retriever = ReportRetriever()

    def get_company_financials(self, company_name: str) -> dict:
        return get_financial_data(company_name)

    def search_company_reports(
        self,
        company_name: str,
        top_k: int = 3,
    ) -> list[dict]:
        query = f"{company_name}의 긍정적인 성장 요인과 투자 근거"

        return self.retriever.search(
            query=query,
            top_k=top_k,
        )