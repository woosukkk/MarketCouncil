from openai import OpenAI

from config import MODEL_NAME, OPENAI_API_KEY
from financial_data import get_financial_data
from bull_prompt import BULL_SYSTEM_PROMPT
from retriever import ReportRetriever


class BullAgent:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.retriever = ReportRetriever()

    def analyze(self, company_name: str) -> tuple[str, dict, list[dict]]:
        financial_data = get_financial_data(company_name)

        query = f"{company_name}의 긍정적인 성장 요인과 투자 근거"

        retrieved_chunks = self.retriever.search(
            query=query,
            top_k=3,
        )

        report_context = "\n\n".join(
            [
                f"""
출처: {chunk["source"]}
청크 번호: {chunk["chunk_id"]}
내용:
{chunk["text"]}
"""
                for chunk in retrieved_chunks
            ]
        )

        user_prompt = f"""
다음 기업을 Bull 관점에서 분석해줘.

기업명: {company_name}
티커: {financial_data["ticker"]}

현재 주가: {financial_data["current_price"]}
주가 기준일: {financial_data["price_date"]}

최근 연간 매출: {financial_data["current_revenue"]}
전년도 매출: {financial_data["previous_revenue"]}
매출 성장률: {financial_data["revenue_growth"]}

최근 연간 영업이익: {financial_data["current_operating_income"]}
전년도 영업이익: {financial_data["previous_operating_income"]}
영업이익 성장률: {financial_data["operating_income_growth"]}

최근 영업이익률: {financial_data["current_operating_margin"]}
전년도 영업이익률: {financial_data["previous_operating_margin"]}

아래는 검색된 투자 리포트 내용이다.

{report_context}

제공된 금융 데이터와 리포트 내용만 근거로
긍정적인 투자 요인과 성장 가능성을 분석해줘.

리포트에서 찾은 근거에는 출처 파일명을 함께 표시해줘.
"""

        response = self.client.responses.create(
            model=MODEL_NAME,
            instructions=BULL_SYSTEM_PROMPT,
            input=user_prompt,
        )

        return response.output_text, financial_data, retrieved_chunks