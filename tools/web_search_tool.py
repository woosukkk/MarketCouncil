from openai import OpenAI

from config import MODEL_NAME, OPENAI_API_KEY

from datetime import datetime, timedelta

from tools.evidence_store import EvidenceStore


class WebSearchTool:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=OPENAI_API_KEY)

    def search_recent_bull_evidence(
        self,
        company_name: str,
    ) -> str:
        prompt = f"""
현재 날짜를 기준으로 {company_name}의 최신 긍정적 투자 근거를 검색해줘.

검색 대상:
- 최근 실적 발표
- 신규 수주
- 신사업 발표
- 생산 확대
- 시장점유율 상승
- 기술 경쟁력
- 기업 공식 발표
- 최근 30일 이내 주요 뉴스

규칙:
1. 최신 자료를 우선한다.
2. 기업 공식 발표, 공시, 주요 언론을 우선한다.
3. 출처명, 게시일, URL을 반드시 표시한다.
4. 같은 사건을 다룬 중복 기사는 하나로 정리한다.
5. 확인되지 않은 사실은 포함하지 않는다.
6. 긍정적인 근거를 최대 5개만 작성한다.

출력 형식:

[근거 1]
- 내용:
- 출처:
- 게시일:
- URL:

자료가 없으면 "최신 긍정 근거 없음"이라고 작성한다.
"""

        response = self.client.responses.create(
            model=MODEL_NAME,
            tools=[
                {
                    "type": "web_search",
                    "search_context_size": "medium",
                }
            ],
            input=prompt,
        )

        return response.output_text

    def search_recent_bear_evidence(
        self,
        company_name: str,
    ) -> str:
        prompt = f"""
현재 날짜를 기준으로 {company_name}의 최신 부정적 투자 근거와 위험 요인을 검색해줘.

검색 대상:
- 최근 실적 악화
- 가이던스 하향
- 경쟁 심화
- 규제
- 소송
- 사고
- 공급 차질
- 수요 감소
- 비용 증가
- 기업 공식 발표
- 최근 30일 이내 주요 뉴스

규칙:
1. 최신 자료를 우선한다.
2. 기업 공식 발표, 공시, 주요 언론을 우선한다.
3. 출처명, 게시일, URL을 반드시 표시한다.
4. 같은 사건을 다룬 중복 기사는 하나로 정리한다.
5. 확인되지 않은 사실은 포함하지 않는다.
6. 부정적인 근거를 최대 5개만 작성한다.

출력 형식:

[근거 1]
- 내용:
- 출처:
- 게시일:
- URL:

자료가 없으면 "최신 부정 근거 없음"이라고 작성한다.
"""

        response = self.client.responses.create(
            model=MODEL_NAME,
            tools=[
                {
                    "type": "web_search",
                    "search_context_size": "medium",
                }
            ],
            input=prompt,
        )

        return response.output_text