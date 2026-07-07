from tools import BullTools


class BullWorkflow:
    def __init__(self) -> None:
        self.tools = BullTools()

    def run(self, company_name: str) -> dict:
        financial_data = self.tools.get_company_financials(
            company_name
        )

        retrieved_chunks = self.tools.search_company_reports(
            company_name,
            top_k=3,
        )

        report_context = "\n\n".join(
            [
                f"""출처: {chunk["source"]}
청크 번호: {chunk["chunk_id"]}
내용:
{chunk["text"]}
"""
                for chunk in retrieved_chunks
            ]
        )

        return {
            "company_name": company_name,
            "financial_data": financial_data,
            "retrieved_chunks": retrieved_chunks,
            "report_context": report_context,
        }