from datetime import datetime
from pathlib import Path

from agents.judge_agent import JudgeAgent


def save_text_result(
    company_name: str,
    perspective: str,
    result: str,
    financial_data: dict,
) -> str:
    results_dir = Path("results") / perspective
    results_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = results_dir / f"{company_name}_{timestamp}.txt"

    content = f"""기업명: {company_name}
분석 관점: {perspective.capitalize()}
분석 시간: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

[금융 데이터]

{financial_data}

[{perspective.capitalize()} 분석 결과]

{result}
"""

    file_path.write_text(
        content,
        encoding="utf-8",
    )

    return str(file_path)


def save_comparison_result(
    analysis_data: dict,
) -> str:
    company_name = analysis_data["company_name"]

    results_dir = Path("results") / "comparison"
    results_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = results_dir / f"{company_name}_{timestamp}.txt"

    content = f"""기업명: {company_name}
분석 유형: Bull/Bear 종합 비교
분석 시간: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

[금융 데이터]

{analysis_data["financial_data"]}

==================================================
[Bull 분석 결과]
==================================================

{analysis_data["bull_result"]}

==================================================
[Bear 분석 결과]
==================================================

{analysis_data["bear_result"]}

==================================================
[Judge 종합 판단]
==================================================

{analysis_data["judge_result"]}
"""

    file_path.write_text(
        content,
        encoding="utf-8",
    )

    return str(file_path)


def main() -> None:
    company_name = input("비교 분석할 기업명: ").strip()

    if not company_name:
        print("기업명을 입력하세요.")
        return

    try:
        judge_agent = JudgeAgent()
        analysis_data = judge_agent.analyze(company_name)

        bull_path = save_text_result(
            company_name=company_name,
            perspective="bull",
            result=analysis_data["bull_result"],
            financial_data=analysis_data["financial_data"],
        )

        bear_path = save_text_result(
            company_name=company_name,
            perspective="bear",
            result=analysis_data["bear_result"],
            financial_data=analysis_data["financial_data"],
        )

        comparison_path = save_comparison_result(
            analysis_data
        )

        print("\n===== Judge 종합 판단 =====\n")
        print(analysis_data["judge_result"])

        print(f"\nBull 저장 완료: {bull_path}")
        print(f"Bear 저장 완료: {bear_path}")
        print(f"Comparison 저장 완료: {comparison_path}")

    except Exception as error:
        print(f"\n오류가 발생했습니다: {error}")


if __name__ == "__main__":
    main()