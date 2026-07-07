from openai import OpenAI

from config import MODEL_NAME, OPENAI_API_KEY
from bull_prompt import BULL_SYSTEM_PROMPT


class BullAgent:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=OPENAI_API_KEY)

    def analyze(self, company_name: str) -> str:
        user_prompt = f"""
다음 기업을 Bull 관점에서 분석해줘.

기업명: {company_name}

확인할 수 있는 긍정적인 투자 근거와 성장 가능성만 분석해줘.
근거가 부족하면 내용을 만들어내지 마.
"""

        response = self.client.responses.create(
            model=MODEL_NAME,
            instructions=BULL_SYSTEM_PROMPT,
            input=user_prompt,
        )

        return response.output_text