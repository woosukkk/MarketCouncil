from openai import OpenAI

from agents.baseline_prompt import BASELINE_SYSTEM_PROMPT
from config import MODEL_NAME, OPENAI_API_KEY


class BaselineAgent:
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
다음 기업의 현재 상태와 확인된 추세를 정리해줘.

기업명: {company_name}

[공통 금융 데이터]

{financial_data}

[통합 로컬 투자 리포트]

{report_context}

[통합 최신 웹 근거]

{web_context}

제공된 자료만 사용해서 정리해줘.
긍정과 부정 방향을 모두 검토하되 특정 방향을 선택하지 마.
웹 근거를 사용할 때는 출처와 게시일을 표시해.
""".strip()

        try:
            response = self.client.responses.create(
                model=MODEL_NAME,
                instructions=BASELINE_SYSTEM_PROMPT,
                input=user_prompt,
            )
        except Exception as error:
            raise RuntimeError(
                f"Baseline 기준선 생성에 실패했습니다: {error}"
            ) from error

        return response.output_text
