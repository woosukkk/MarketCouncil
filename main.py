from datetime import datetime
from pathlib import Path

from bull_agent import BullAgent


def save_result(company_name: str, result: str) -> None:
    results_dir = Path("results")
    results_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = company_name.replace(" ", "_")

    file_path = results_dir / f"{safe_name}_{timestamp}.txt"

    content = f"""기업명: {company_name}
분석 시간: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

{result}
"""

    file_path.write_text(content, encoding="utf-8")

    print(f"\n결과 저장 완료: {file_path}")


def main() -> None:
    company_name = input("분석할 기업명: ").strip()

    if not company_name:
        print("기업명을 입력하세요.")
        return

    try:
        agent = BullAgent()
        result = agent.analyze(company_name)

        print("\n===== Bull 분석 결과 =====\n")
        print(result)

        save_result(company_name, result)

    except Exception as error:
        print(f"오류가 발생했습니다: {error}")


if __name__ == "__main__":
    main()