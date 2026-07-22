from agents.video_debate_agent import VideoDebateAgent
from tools.video_debate_store import VideoDebateStore


DEFAULT_BEAR_VIDEO = "https://www.youtube.com/watch?v=ecBM7yxXvF0"
DEFAULT_BULL_VIDEO = "https://www.youtube.com/watch?v=Yy3aOAAUza0"


def main() -> None:
    company_name = input("영상 토론 대상 기업명: ").strip()
    if not company_name:
        print("기업명을 입력하세요.")
        return

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
        result_path = VideoDebateStore().save(
            company_name,
            result,
        )
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
    print(f"\n저장 완료: {result_path}")
    print("최종 판단은 compare_main 실행 시 Judge가 수행합니다.")


if __name__ == "__main__":
    main()
