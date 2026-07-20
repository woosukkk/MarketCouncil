from tools.report_candidate_collector import ReportCandidateCollector


def main() -> None:
    company_name = input("리포트를 수집할 기업명: ").strip()
    if not company_name:
        print("기업명을 입력하세요.")
        return

    ticker = input("티커(선택): ").strip()

    try:
        result = ReportCandidateCollector().collect(
            company_name,
            ticker=ticker or None,
        )
    except Exception as error:
        print(f"\n리포트 자동 수집 오류: {error}")
        return

    print("\n===== 자동 수집 결과 =====")
    print(f"검토 대기 등록: {len(result['queued'])}개")
    print(f"중복 또는 기존 등록: {len(result['skipped'])}개")
    print(f"다운로드 실패: {len(result['failed'])}개")

    for failure in result["failed"]:
        print(f"- 실패: {failure['url']} ({failure['reason']})")

    print("\n검토 화면에서 승인 또는 거절하세요:")
    print(
        ".\\venv\\Scripts\\python.exe -m streamlit "
        "run app\\document_review.py"
    )


if __name__ == "__main__":
    main()
