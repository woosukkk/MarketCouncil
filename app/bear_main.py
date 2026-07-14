from agents.bear_agent import BearAgent


def main() -> None:
    company_name = input("분석할 기업명: ").strip()

    if not company_name:
        print("기업명을 입력하세요.")
        return

    try:
        agent = BearAgent()

        result, _, _ = agent.analyze(company_name)

        print("\n===== Bear 분석 결과 =====\n")
        print(result)

    except Exception as error:
        print(f"오류가 발생했습니다: {error}")


if __name__ == "__main__":
    main()