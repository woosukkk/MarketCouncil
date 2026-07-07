from openai import OpenAI

from config import MODEL_NAME, OPENAI_API_KEY
from financial_data import get_financial_data
from bull_prompt import BULL_SYSTEM_PROMPT


class BullAgent:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=OPENAI_API_KEY)

    def analyze(self, company_name: str) -> str:
        financial_data = get_financial_data(company_name)

        user_prompt = f"""
다음 기업을 Bull 관점에서 분석해줘.

기업명: {company_name}
티커: {financial_data["ticker"]}
현재 주가: {financial_data["current_price"]}
최근 연간 매출: {financial_data["revenue"]}
최근 연간 영업이익: {financial_data["operating_income"]}

제공된 금융 데이터와 확인 가능한 일반 정보만 사용해서
긍정적인 투자 근거와 성장 가능성을 분석해줘.

근거가 부족하면 내용을 만들어내지 마.
"""

        response = self.client.responses.create(
            model=MODEL_NAME,
            instructions=BULL_SYSTEM_PROMPT,
            input=user_prompt,
        )

        return response.output_text