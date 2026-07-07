from datetime import datetime
from pathlib import Path

from bull_agent import BullAgent


def save_result(
    company_name: str,
    result: str,
    financial_data: dict,
    retrieved_chunks: list[dict],
) -> None:
    results_dir = Path("results")
    results_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = company_name.replace(" ", "_")
    file_path = results_dir / f"{safe_name}_{timestamp}.txt"

    retrieved_text = "\n\n".join(
        [
            f"""출처: {chunk["source"]}
청크 번호: {chunk["chunk_id"]}
거리: {chunk["distance"]}
내용:
{chunk["text"]}
"""
            for chunk in retrieved_chunks
        ]
    )

    content = f"""기업명: {company_name}
티커: {financial_data["ticker"]}
분석 시간: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

[사용된 금융 데이터]
현재 주가: {financial_data["current_price"]}
주가 기준일: {financial_data.get("price_date", "데이터 없음")}
최근 연간 매출: {financial_data["current_revenue"]}
전년도 매출: {financial_data["previous_revenue"]}
매출 성장률: {financial_data["revenue_growth"]}
최근 연간 영업이익: {financial_data["current_operating_income"]}
전년도 영업이익: {financial_data["previous_operating_income"]}
영업이익 성장률: {financial_data["operating_income_growth"]}
최근 영업이익률: {financial_data["current_operating_margin"]}
전년도 영업이익률: {financial_data["previous_operating_margin"]}

[검색된 리포트 근거]

{retrieved_text}

[Bull 분석 결과]

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

        result, financial_data, retrieved_chunks = agent.analyze(
            company_name
        )

        print("\n===== Bull 분석 결과 =====\n")
        print(result)

        save_result(
            company_name,
            result,
            financial_data,
            retrieved_chunks,
        )

    except Exception as error:
        print(f"오류가 발생했습니다: {error}")


if __name__ == "__main__":
    main()