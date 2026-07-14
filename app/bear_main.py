from datetime import datetime
from pathlib import Path

from agents.bear_agent import BearAgent


def save_bear_result(
    company_name: str,
    result: str,
    financial_data: dict,
    retrieved_chunks: list[dict],
) -> str:
    results_dir = Path("results")
    results_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = results_dir / f"{company_name}_bear_{timestamp}.txt"

    chunk_text = "\n\n".join(
        f"""출처: {chunk["source"]}
청크 번호: {chunk["chunk_id"]}
내용:
{chunk["text"]}"""
        for chunk in retrieved_chunks
    )

    content = f"""기업명: {company_name}
분석 관점: Bear
분석 시간: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

[금융 데이터]

{financial_data}

[검색된 리포트 청크]

{chunk_text}

[Bear 분석 결과]

{result}
"""

    file_path.write_text(
        content,
        encoding="utf-8",
    )

    return str(file_path)


def main() -> None:
    company_name = input("분석할 기업명: ").strip()

    if not company_name:
        print("기업명을 입력하세요.")
        return

    try:
        agent = BearAgent()

        result, financial_data, retrieved_chunks = agent.analyze(
            company_name
        )

        print("\n===== Bear 분석 결과 =====\n")
        print(result)

        saved_path = save_bear_result(
            company_name,
            result,
            financial_data,
            retrieved_chunks,
        )

        print(f"\n저장 완료: {saved_path}")

    except Exception as error:
        print(f"오류가 발생했습니다: {error}")


if __name__ == "__main__":
    main()