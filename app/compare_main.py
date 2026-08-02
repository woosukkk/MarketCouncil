from datetime import datetime
from pathlib import Path

from agents.judge_agent import JudgeAgent
from agents.report_agent import HumanReadableReportAgent
from tools.analysis_debate_store import AnalysisDebateStore
from tools.markdown_report_renderer import (
    MarkdownReportRenderer,
    humanize_judge_result,
)
from tools.video_debate_store import VideoDebateStore


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


def choose_debate_mode(
    company_name: str,
) -> tuple[str, dict | None]:
    store = AnalysisDebateStore()
    try:
        latest_debate = store.load_latest(company_name)
    except ValueError as error:
        print(f"최근 토론 결과 확인 오류: {error}")
        latest_debate = None

    print("\n===== 토론 적용 방식 선택 =====")
    if latest_debate:
        created_at = str(latest_debate.get("created_at", ""))
        age_text, age_days = _format_debate_age(created_at)
        print(f"최근 토론 생성일: {created_at or '알 수 없음'}")
        print(f"현재 기준: {age_text}")
        print(f"토론 라운드: {len(latest_debate.get('rounds', []))}회")
        if age_days is not None and age_days >= 8:
            print("주의: 8일 이상 지난 토론으로 최신성이 낮을 수 있습니다.")
        elif age_days is not None and age_days >= 4:
            print("주의: 4일 이상 지난 토론입니다.")
        print("\n1. 토론 없이 Judge 실행 (기본값)")
        print("2. 최근 토론 결과를 Judge에 적용")
        print("3. 현재 분석으로 새 토론 후 Judge에 적용")
        valid_choices = {"1", "2", "3"}
    else:
        print("저장된 토론 결과가 없습니다.")
        print("\n1. 토론 없이 Judge 실행 (기본값)")
        print("3. 현재 분석으로 새 토론 후 Judge에 적용")
        valid_choices = {"1", "3"}

    while True:
        choice = input("선택 (기본값 1): ").strip() or "1"
        if choice in valid_choices:
            break
        print("표시된 번호 중 하나를 입력하세요.")

    if choice == "2":
        return "existing", latest_debate
    if choice == "3":
        return "new", None
    return "none", None


def _format_debate_age(created_at: str) -> tuple[str, int | None]:
    try:
        created = datetime.fromisoformat(created_at)
    except (TypeError, ValueError):
        return "생성일 확인 불가", None
    now = datetime.now(created.tzinfo) if created.tzinfo else datetime.now()
    age_days = max((now.date() - created.date()).days, 0)
    if age_days == 0:
        return "오늘 생성", 0
    return f"{age_days}일 전", age_days


def main() -> None:
    company_name = input("비교 분석할 기업명: ").strip()

    if not company_name:
        print("기업명을 입력하세요.")
        return

    debate_mode, existing_debate = choose_debate_mode(company_name)

    video_debate = None
    try:
        latest_video_debate = VideoDebateStore().load_latest(company_name)
    except ValueError as error:
        print(f"영상 분석 결과 확인 오류: {error}")
        latest_video_debate = None

    if latest_video_debate:
        created_at = latest_video_debate.get("created_at", "알 수 없음")
        print(f"최신 영상 분석 결과 발견: {created_at}")
        use_video = input(
            "최종 Judge 판단에 영상 요약을 포함할까요? (y/N): "
        ).strip().lower()
        if use_video in {"y", "yes"}:
            video_debate = latest_video_debate

    try:
        judge_agent = JudgeAgent()
        analysis_data = judge_agent.analyze(
            company_name,
            video_debate=video_debate,
            debate_mode=debate_mode,
            existing_debate=existing_debate,
        )

        analysis_debate = analysis_data.get("analysis_debate", {})
        debate_path = ""
        if analysis_debate:
            if analysis_data.get("debate_source") == "newly_generated":
                debate_path = AnalysisDebateStore().save(
                    company_name,
                    analysis_debate,
                    included_in_judge=True,
                )

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

        markdown_renderer = MarkdownReportRenderer()
        print("\n[사람 중심 Markdown 보고서 생성 시작]")
        try:
            markdown_content = HumanReadableReportAgent().generate(
                analysis_data
            )
            print("[사람 중심 Markdown 보고서 생성 완료]")
        except RuntimeError as error:
            print(f"[WARN] LLM 보고서 생성 실패: {error}")
            print("[WARN] 규칙 기반 Markdown 보고서로 대체합니다.")
            markdown_content = markdown_renderer.render(analysis_data)
        markdown_content = markdown_renderer.normalize_generated(
            markdown_content
        )
        comparison_path = markdown_renderer.save_content(
            company_name,
            markdown_content,
        )

        print("\n===== Judge 종합 판단 =====\n")
        print(humanize_judge_result(analysis_data["judge_result"]))

        print("\n개별 관점 분석 원본 저장 완료")
        print(f"Markdown 최종 결과 저장 완료: {comparison_path}")
        if debate_path:
            print(f"새 토론 결과 저장 완료: {debate_path}")
        if analysis_data.get("debate_applied"):
            print("토론 핵심 결과가 HTML 보고서와 Judge 판단에 적용되었습니다.")
        else:
            print("토론 결과를 생성하거나 Judge 판단에 적용하지 않았습니다.")

    except Exception as error:
        print(f"\n오류가 발생했습니다: {error}")


if __name__ == "__main__":
    main()
