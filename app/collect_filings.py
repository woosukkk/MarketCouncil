from tools.regulatory_filing_collector import RegulatoryFilingCollector


def main() -> None:
    market = input("시장 (kr/us): ").strip().lower()
    company_name = input("기업명: ").strip()
    ticker = input("티커: ").strip()

    if market not in {"kr", "us"}:
        print("시장은 kr 또는 us로 입력하세요.")
        return
    if not company_name or not ticker:
        print("기업명과 티커를 모두 입력하세요.")
        return

    try:
        result = RegulatoryFilingCollector().collect(
            market=market,
            company_name=company_name,
            ticker=ticker,
        )
    except Exception as error:
        print(f"\n공시 수집 오류: {error}")
        return

    print("\n===== 공식 공시 수집 결과 =====")
    print(f"공급자: {result['provider']}")
    print(f"원문 다운로드: {len(result['downloaded'])}개")
    print(f"기존 파일 건너뜀: {len(result['skipped'])}개")
    print(f"다운로드 실패: {len(result['failed'])}개")

    for failure in result["failed"]:
        print(f"- 실패: {failure['id']} ({failure['reason']})")

    print("\n저장 위치: documents/regulatory")
    print("이 단계에서는 LLM을 호출하거나 RAG에 자동 등록하지 않습니다.")


if __name__ == "__main__":
    main()
