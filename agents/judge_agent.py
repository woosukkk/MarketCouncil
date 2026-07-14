from openai import OpenAI

from agents.bear_agent import BearAgent
from agents.bull_agent import BullAgent
from agents.judge_prompt import JUDGE_SYSTEM_PROMPT
from config import MODEL_NAME, OPENAI_API_KEY


class JudgeAgent:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.bull_agent = BullAgent()
        self.bear_agent = BearAgent()

    def analyze(
        self,
        company_name: str,
    ) -> dict:
        print("\n[1] Bull Agent 분석 시작")

        (
            bull_result,
            bull_financial_data,
            bull_chunks,
        ) = self.bull_agent.analyze(company_name)

        print("[1] Bull Agent 분석 완료")

        print("\n[2] Bear Agent 분석 시작")

        (
            bear_result,
            bear_financial_data,
            bear_chunks,
        ) = self.bear_agent.analyze(company_name)

        print("[2] Bear Agent 분석 완료")

        print("\n[3] Judge Agent 비교 시작")

        user_prompt = f"""
다음은 동일한 기업에 대한 Bull 분석과 Bear 분석이다.

기업명: {company_name}

[공통 금융 데이터]

{bull_financial_data}

[Bull 분석]

{bull_result}

[Bear 분석]

{bear_result}

두 분석에서 사용한 근거의 구체성, 출처 신뢰도, 날짜,
금융 데이터와의 연결성을 비교해 최종 종합 의견을 작성해줘.

다음 기준을 반드시 적용해:
- 출처와 날짜가 명확한 근거를 우선한다.
- 같은 사건을 반복한 주장은 하나의 근거로 본다.
- 단순한 가능성만 제시한 주장은 낮게 평가한다.
- 일반적인 면책 문구나 모든 기업에 적용되는 위험은 낮게 평가한다.
- 긍정적 근거와 부정적 근거가 모두 강하면 Neutral로 판단할 수 있다.
- Bull Score와 Bear Score의 합은 100으로 작성한다.
"""

        response = self.client.responses.create(
            model=MODEL_NAME,
            instructions=JUDGE_SYSTEM_PROMPT,
            input=user_prompt,
        )

        print("[3] Judge Agent 비교 완료")

        return {
            "company_name": company_name,
            "financial_data": bull_financial_data,
            "bull_result": bull_result,
            "bear_result": bear_result,
            "judge_result": response.output_text,
            "bull_chunks": bull_chunks,
            "bear_chunks": bear_chunks,
        }