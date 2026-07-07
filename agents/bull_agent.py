from openai import OpenAI

from config import MODEL_NAME, OPENAI_API_KEY
from agents.bull_prompt import BULL_SYSTEM_PROMPT
from app.workflow import BullWorkflow

class BullAgent:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.workflow = BullWorkflow()

    def analyze(self, company_name: str) -> tuple[str, dict, list[dict]]:
        workflow_result = self.workflow.run(company_name)

        financial_data = workflow_result["financial_data"]
        retrieved_chunks = workflow_result["retrieved_chunks"]
        report_context = workflow_result["report_context"]

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

[검색된 투자 리포트]

{report_context}

제공된 금융 데이터와 리포트 내용만 근거로
긍정적인 투자 요인과 성장 가능성을 분석해줘.

검색된 청크에 없는 수치나 정보는 추가하지 마.
"""

        response = self.client.responses.create(
            model=MODEL_NAME,
            instructions=BULL_SYSTEM_PROMPT,
            input=user_prompt,
        )

        return (
            response.output_text,
            financial_data,
            retrieved_chunks,
        )