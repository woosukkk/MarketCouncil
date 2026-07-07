import os

from dotenv import load_dotenv
from openai import OpenAI

from bull_prompt import BULL_SYSTEM_PROMPT


def create_client() -> OpenAI:
    """
    .env 파일에서 OpenAI API 키를 불러와 클라이언트를 생성한다.
    """
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY가 없습니다. "
            ".env 파일에 OPENAI_API_KEY를 입력하세요."
        )

    return OpenAI(api_key=api_key)


def analyze_company(client: OpenAI, company_name: str) -> str:
    """
    입력받은 기업을 Bull 관점으로 분석한다.
    """
    user_prompt = f"""
다음 기업을 Bull 관점에서 분석해줘.

기업명: {company_name}

현재 외부 금융 데이터나 실시간 뉴스는 제공되지 않았다.
따라서 알고 있는 일반적인 기업 정보만 사용하고,
확실하지 않은 최신 수치나 사건은 만들어내지 마라.
"""

    response = client.responses.create(
        model="gpt-5-mini",
        instructions=BULL_SYSTEM_PROMPT,
        input=user_prompt,
    )

    return response.output_text


def main() -> None:
    try:
        client = create_client()

        print("=" * 50)
        print("Bull Investment Analysis Agent v1")
        print("=" * 50)

        company_name = input("분석할 기업명을 입력하세요: ").strip()

        if not company_name:
            print("기업명을 입력해야 합니다.")
            return

        print("\nBull Agent가 분석 중입니다.\n")

        result = analyze_company(client, company_name)

        print(result)

    except Exception as error:
        print(f"\n오류가 발생했습니다: {error}")


if __name__ == "__main__":
    main()