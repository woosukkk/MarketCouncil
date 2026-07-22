import json
from datetime import datetime
from pathlib import Path

from agents.video_debate_agent import VideoDebateAgent


DEFAULT_BEAR_VIDEO = "https://www.youtube.com/watch?v=ecBM7yxXvF0"
DEFAULT_BULL_VIDEO = "https://www.youtube.com/watch?v=Yy3aOAAUza0"


def save_result(result: dict) -> str:
    results_dir = Path("results") / "video_debate"
    results_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = results_dir / f"video_debate_{timestamp}.json"
    file_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(file_path)


def main() -> None:
    bull_url = input(
        f"낙관(Bull) 영상 URL [{DEFAULT_BULL_VIDEO}]: "
    ).strip() or DEFAULT_BULL_VIDEO
    bear_url = input(
        f"비관(Bear) 영상 URL [{DEFAULT_BEAR_VIDEO}]: "
    ).strip() or DEFAULT_BEAR_VIDEO

    try:
        result = VideoDebateAgent().run(
            bull_video_url=bull_url,
            bear_video_url=bear_url,
        )
        result_path = save_result(result)
    except Exception as error:
        print(f"\n영상 토론 오류: {error}")
        return

    print("\n===== Bull 영상 요약 =====\n")
    print(result["bull_summary"])
    print("\n===== Bear 영상 요약 =====\n")
    print(result["bear_summary"])
    print("\n===== Bull의 Bear 반박 =====\n")
    print(result["bull_rebuttal"])
    print("\n===== Bear의 Bull 반박 =====\n")
    print(result["bear_rebuttal"])
    print("\n===== Judge 종합 평가 =====\n")
    print(result["judge_result"])
    print(f"\n저장 완료: {result_path}")


if __name__ == "__main__":
    main()
