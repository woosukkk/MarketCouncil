import json
from datetime import datetime
from pathlib import Path

from agents.judge_agent import JudgeAgent
from tools.analysis_debate_store import AnalysisDebateStore
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


def save_comparison_result(
    analysis_data: dict,
) -> str:
    company_name = analysis_data["company_name"]

    results_dir = Path("results") / "comparison"
    results_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = results_dir / f"{company_name}_{timestamp}.txt"

    video_debate_section = ""
    if analysis_data.get("video_debate"):
        video_debate = analysis_data["video_debate"]
        video_debate_section = f"""
==================================================
[영상 관점별 요약]
==================================================

Bull 영상 요약:
{video_debate.get("bull_summary", "")}

Bear 영상 요약:
{video_debate.get("bear_summary", "")}
"""

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
[뉴스 민심 분석]
==================================================

{json.dumps(analysis_data["sentiment_result"], ensure_ascii=False, indent=2)}

{video_debate_section}

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


def print_debate_result(debate: dict) -> None:
    print("\n" + "=" * 72)
    print("[중재 토론 의제]")
    print("=" * 72)
    for index, issue in enumerate(debate.get("agenda", []), start=1):
        print(f"\n쟁점 {index}. {issue.get('title', '')}")
        print(f"  Bull 최초 주장: {issue.get('bull_claim', '')}")
        print(f"  Bear 최초 주장: {issue.get('bear_claim', '')}")
        print(f"  중재자 질문: {issue.get('question', '')}")

    for round_data in debate.get("rounds", []):
        round_number = round_data.get("round", "?")
        print("\n" + "=" * 72)
        print(f"[토론 {round_number}라운드]")
        print("=" * 72)
        _print_debate_turn("Bull", round_data.get("bull_response", {}))
        _print_debate_turn("Bear", round_data.get("bear_response", {}))

        review = round_data.get("moderator_review", {})
        print("\n  [중재자 검토]")
        for issue in review.get("issue_reviews", []):
            print(
                f"  - {issue.get('issue_id', '')} "
                f"[{issue.get('status', '')}]: "
                f"{issue.get('assessment', '')}"
            )
            if issue.get("question_for_bull"):
                print(f"    Bull에게: {issue['question_for_bull']}")
            if issue.get("question_for_bear"):
                print(f"    Bear에게: {issue['question_for_bear']}")
        print(f"  계속 여부: {review.get('continue_debate', False)}")
        print(f"  판단 이유: {review.get('reason', '')}")

    summary = debate.get("moderator_summary", {})
    print("\n" + "=" * 72)
    print("[중재자 최종 정리]")
    print("=" * 72)
    print(f"종료 이유: {debate.get('stop_reason', '')}")
    _print_list("합의점", summary.get("agreements", []))
    _print_list("미해결 쟁점", summary.get("unresolved_issues", []))
    _print_list("추가 필요 증거", summary.get("required_evidence", []))
    print(f"요약: {summary.get('summary', '')}")


def _print_debate_turn(role: str, turn: dict) -> None:
    print(f"\n  [{role} 발언]")
    print(f"  입장 요약: {turn.get('position_summary', '')}")
    for index, issue in enumerate(turn.get("issues", []), start=1):
        print(f"\n  {role} 쟁점 {index} ({issue.get('issue_id', '')})")
        print(f"    상대 주장: {issue.get('target_claim', '')}")
        print(f"    반론: {issue.get('response', '')}")
        _print_list("반론 근거", issue.get("evidence", []), indent="    ")
        print(f"    인정하는 부분: {issue.get('concession', '')}")
        print(f"    추가 확인 필요: {issue.get('missing_evidence', '')}")


def _print_list(label: str, items: list, indent: str = "") -> None:
    print(f"{indent}{label}:")
    if not items:
        print(f"{indent}  - 없음")
        return
    for item in items:
        print(f"{indent}  - {item}")


def main() -> None:
    company_name = input("비교 분석할 기업명: ").strip()

    if not company_name:
        print("기업명을 입력하세요.")
        return

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
        )

        analysis_debate = analysis_data.get("analysis_debate", {})
        debate_path = ""
        if analysis_debate:
            print_debate_result(analysis_debate)
            debate_path = AnalysisDebateStore().save(
                company_name,
                analysis_debate,
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

        comparison_path = save_comparison_result(
            analysis_data
        )

        print("\n===== Judge 종합 판단 =====\n")
        print(analysis_data["judge_result"])

        print(f"\nBull 저장 완료: {bull_path}")
        print(f"Bear 저장 완료: {bear_path}")
        print(f"Comparison 저장 완료: {comparison_path}")
        if debate_path:
            print(f"토론 실험 결과 별도 저장 완료: {debate_path}")
            print("토론 결과는 Judge 판단과 Comparison 결과에 포함되지 않았습니다.")

    except Exception as error:
        print(f"\n오류가 발생했습니다: {error}")


if __name__ == "__main__":
    main()
