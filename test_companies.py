from bull_agent import BullAgent
from main import save_result


TEST_COMPANIES = [
    "삼성전자",
    "SK하이닉스",
    "현대자동차",
]


def main() -> None:
    agent = BullAgent()

    for company_name in TEST_COMPANIES:
        print(f"\n===== {company_name} 분석 시작 =====")

        try:
            result = agent.analyze(company_name)
            print(result)

            save_result(company_name, result)

        except Exception as error:
            print(f"{company_name} 분석 실패: {error}")


if __name__ == "__main__":
    main()