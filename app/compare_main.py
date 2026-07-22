import json
from datetime import datetime
from pathlib import Path

from agents.judge_agent import JudgeAgent
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
[영상 토론 분석]
==================================================

Bull 영상 요약:
{video_debate.get("bull_summary", "")}

Bear 영상 요약:
{video_debate.get("bear_summary", "")}

Bull 반박:
{video_debate.get("bull_rebuttal", "")}

Bear 반박:
{video_debate.get("bear_rebuttal", "")}
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


def main() -> None:
    company_name = input("비교 분석할 기업명: ").strip()

    if not company_name:
        print("기업명을 입력하세요.")
        return

    video_debate = None
    try:
        latest_video_debate = VideoDebateStore().load_latest(company_name)
    except ValueError as error:
        print(f"영상 토론 결과 확인 오류: {error}")
        latest_video_debate = None

    if latest_video_debate:
        created_at = latest_video_debate.get("created_at", "알 수 없음")
        print(f"최신 영상 토론 결과 발견: {created_at}")
        use_video = input(
            "최종 Judge 판단에 영상 토론을 포함할까요? (y/N): "
        ).strip().lower()
        if use_video in {"y", "yes"}:
            video_debate = latest_video_debate

    try:
        judge_agent = JudgeAgent()
        analysis_data = judge_agent.analyze(
            company_name,
            video_debate=video_debate,
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

    except Exception as error:
        print(f"\n오류가 발생했습니다: {error}")


if __name__ == "__main__":
    main()
