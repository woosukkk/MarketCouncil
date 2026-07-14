from openai import OpenAI

from agents.bear_prompt import BEAR_SYSTEM_PROMPT
from app.bear_langgraph_workflow import BearGraphWorkflow
from config import MODEL_NAME, OPENAI_API_KEY


class BearAgent:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.workflow = BearGraphWorkflow()

    def analyze(
        self,
        company_name: str,
    ) -> tuple[str, dict, list[dict]]:
        workflow_result = self.workflow.run(company_name)

        financial_data = workflow_result["financial_data"]
        retrieved_chunks = workflow_result["retrieved_chunks"]
        report_context = workflow_result["report_context"]
        web_context = workflow_result["web_context"]

        user_prompt = f"""
다음 기업을 Bear 관점에서 분석해줘.

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

[최신 웹 검색 결과]

{web_context}

금융 데이터, 로컬 리포트, 최신 웹 검색 결과만 근거로 분석해줘.

최신 웹 근거를 사용할 때는 반드시 출처와 게시일을 표시해.
검색 결과에 없는 사실은 추가하지 마.
"""

        response = self.client.responses.create(
            model=MODEL_NAME,
            instructions=BEAR_SYSTEM_PROMPT,
            input=user_prompt,
        )

        return (
            response.output_text,
            financial_data,
            retrieved_chunks,
        )