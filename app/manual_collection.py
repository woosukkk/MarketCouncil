from typing import Any

from tools.regulatory_filing_collector import RegulatoryFilingCollector
from tools.regulatory_filing_candidate_collector import (
    RegulatoryFilingCandidateCollector,
)
from tools.report_candidate_collector import ReportCandidateCollector


def _print_filing_result(result: dict[str, Any]) -> None:
    print(f"공급자: {result.get('provider', '확인 불가')}")
    print(f"원문 다운로드: {len(result.get('downloaded', []))}개")
    print(f"기존 파일 건너뜀: {len(result.get('skipped', []))}개")
    print(f"다운로드 실패: {len(result.get('failed', []))}개")

    for failure in result.get("failed", []):
        print(
            f"- 실패: {failure.get('id', '확인 불가')} "
            f"({failure.get('reason', '원인 확인 불가')})"
        )


def _print_report_result(result: dict[str, Any]) -> None:
    print(f"검토 대기 등록: {len(result.get('queued', []))}개")
    print(f"중복 또는 기존 등록: {len(result.get('skipped', []))}개")
    print(f"다운로드 실패: {len(result.get('failed', []))}개")

    for failure in result.get("failed", []):
        print(
            f"- 실패: {failure.get('url', '확인 불가')} "
            f"({failure.get('reason', '원인 확인 불가')})"
        )


def main() -> int:
    print("===== 수동 공시·리포트 수집 =====")
    market = input("시장 (kr/us): ").strip().lower()
    company_name = input("기업명: ").strip()
    ticker = input("티커: ").strip()

    if market not in {"kr", "us"}:
        print("[ERROR] 시장은 kr 또는 us로 입력하세요.")
        return 1
    if not company_name or not ticker:
        print("[ERROR] 기업명과 티커를 모두 입력하세요.")
        return 1

    failed = False

    print("\n[1/2] 공식 공시 수집 시작")
    try:
        filing_result = RegulatoryFilingCollector().collect(
            market=market,
            company_name=company_name,
            ticker=ticker,
        )
    except Exception as error:
        failed = True
        print(f"[ERROR] 공식 공시 수집 실패: {error}")
    else:
        _print_filing_result(filing_result)
        print("공시 저장 위치: documents/regulatory")
        if filing_result.get("failed"):
            failed = True

    print("\n[공시 검토 대기 등록 시작]")
    try:
        filing_queue = RegulatoryFilingCandidateCollector().queue_available(
            provider="open_dart" if market == "kr" else "sec_edgar",
            company_name=company_name,
        )
    except Exception as error:
        failed = True
        print(f"[ERROR] 공시 검토 대기 등록 실패: {error}")
    else:
        print(f"검토 대기 등록: {len(filing_queue['queued'])}개")
        print(f"기존 등록 건너뜀: {len(filing_queue['skipped'])}개")
        print(f"본문 추출·등록 실패: {len(filing_queue['failed'])}개")
        for failure in filing_queue["failed"]:
            print(
                f"- 실패: {failure.get('id', '확인 불가')} "
                f"({failure.get('reason', '원인 확인 불가')})"
            )
        if filing_queue["failed"]:
            failed = True

    print("\n[2/2] 공식 문서·전문 리포트 수집 시작")
    try:
        report_result = ReportCandidateCollector().collect(
            company_name=company_name,
            ticker=ticker,
        )
    except Exception as error:
        failed = True
        print(f"[ERROR] 리포트 수집 실패: {error}")
    else:
        _print_report_result(report_result)
        print("리포트 검토 대기 위치: documents/inbox")
        if report_result.get("failed"):
            failed = True

    print("\n수집 단계를 마쳤습니다. 문서 검토 화면을 엽니다.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
