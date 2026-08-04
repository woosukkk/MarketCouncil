from openai import OpenAI

from agents.neutral_prompt import NEUTRAL_SYSTEM_PROMPT
from config import MODEL_NAME, OPENAI_API_KEY


class NeutralAgent:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=OPENAI_API_KEY)

    def analyze_with_context(
        self,
        company_name: str,
        financial_data: dict,
        report_context: str,
        web_context: str,
    ) -> str:
        user_prompt = f"""
다음 기업의 증거 기반 기본 시나리오를 작성해줘.

기업명: {company_name}

[공통 금융 데이터]

{financial_data}

[통합 로컬 투자 리포트]

{report_context}

[통합 최신 웹 근거]

{web_context}

제공된 자료만 사용해서 분석해줘.
긍정과 부정 방향을 모두 검토하되 특정 결론을 설득하지 마.
웹 근거를 사용할 때는 출처와 게시일을 표시해.
""".strip()

        try:
            response = self.client.responses.create(
                model=MODEL_NAME,
                instructions=NEUTRAL_SYSTEM_PROMPT,
                input=user_prompt,
            )
        except Exception as error:
            raise RuntimeError(
                f"Neutral 기본 시나리오 생성에 실패했습니다: {error}"
            ) from error

        return response.output_text
