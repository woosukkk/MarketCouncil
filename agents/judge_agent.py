import json

from openai import OpenAI

from agents.bear_agent import BearAgent
from agents.bull_agent import BullAgent
from agents.judge_prompt import JUDGE_SYSTEM_PROMPT
from agents.sentiment_agent import SentimentAgent
from app.comparison_workflow import ComparisonWorkflow
from config import MODEL_NAME, OPENAI_API_KEY


class JudgeAgent:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=OPENAI_API_KEY)

        self.workflow = ComparisonWorkflow()
        self.bull_agent = BullAgent()
        self.bear_agent = BearAgent()
        self.sentiment_agent = SentimentAgent()

    def analyze(
        self,
        company_name: str,
    ) -> dict:
        print("\n[공통 데이터 수집 시작]")

        context = self.workflow.run(company_name)

        print("[공통 데이터 수집 완료]")

        financial_data = context["financial_data"]

        print("\n[Bull Agent 분석 시작]")

        bull_result = self.bull_agent.analyze_with_context(
            company_name=company_name,
            financial_data=financial_data,
            report_context=context[
                "bull_report_context"
            ],
            web_context=context[
                "bull_web_context"
            ],
        )

        print("[Bull Agent 분석 완료]")

        print("\n[Bear Agent 분석 시작]")

        bear_result = self.bear_agent.analyze_with_context(
            company_name=company_name,
            financial_data=financial_data,
            report_context=context[
                "bear_report_context"
            ],
            web_context=context[
                "bear_web_context"
            ],
        )

        print("[Bear Agent 분석 완료]")

        print("\n[민심 Agent 분석 시작]")

        sentiment_result = self.sentiment_agent.analyze(
            company_name
        )

        print("[민심 Agent 분석 완료]")

        print("\n[Judge Agent 비교 시작]")

        user_prompt = f"""
다음은 동일한 기업과 동일한 금융 데이터에 기반한
Bull 분석과 Bear 분석이다.

기업명: {company_name}

[공통 금융 데이터]

{financial_data}

[Bull 분석]

{bull_result}

[Bear 분석]

{bear_result}

[뉴스 민심 분석]

{json.dumps(sentiment_result, ensure_ascii=False, indent=2)}

두 분석의 근거 구체성, 출처 신뢰도, 날짜,
금융 데이터와의 연결성을 비교해
최종 종합 의견을 작성해줘.

규칙:
- 근거 개수보다 품질을 우선한다.
- 같은 사건을 반복한 주장은 하나로 본다.
- 일반적인 면책 문구는 약한 근거로 평가한다.
- 출처와 날짜가 명확한 근거를 높게 평가한다.
- 뉴스 민심 비율은 보조 지표로만 사용한다.
- 기사 수만으로 Bull/Bear 점수를 결정하지 않는다.
- Bull Score와 Bear Score의 합은 100으로 작성한다.
"""

        response = self.client.responses.create(
            model=MODEL_NAME,
            instructions=JUDGE_SYSTEM_PROMPT,
            input=user_prompt,
        )

        print("[Judge Agent 비교 완료]")

        return {
            "company_name": company_name,
            "financial_data": financial_data,
            "bull_result": bull_result,
            "bear_result": bear_result,
            "sentiment_result": sentiment_result,
            "judge_result": response.output_text,
            "bull_chunks": context.get(
                "bull_chunks",
                [],
            ),
            "bear_chunks": context.get(
                "bear_chunks",
                [],
            ),
            "bull_web_context": context.get(
                "bull_web_context",
                "",
            ),
            "bear_web_context": context.get(
                "bear_web_context",
                "",
            ),
        }
