import sys

from app.debate_workflow import DebateWorkflow
from app.local_services import ensure_local_services
from tools.analysis_debate_store import AnalysisDebateStore
from tools.debate_transcript_renderer import DebateTranscriptRenderer


def main() -> int:
    try:
        ensure_local_services()
    except RuntimeError as error:
        print(f"\n오픈소스 서비스 준비 오류: {error}")
        return 1

    if "--check" in sys.argv[1:]:
        print("Docker와 SearXNG가 준비되었습니다.")
        return 0

    company_name = input("토론할 기업명: ").strip()
    if not company_name:
        print("기업명을 입력하세요.")
        return 1

    try:
        debate = DebateWorkflow().run(company_name)
        json_path = AnalysisDebateStore().save(company_name, debate)
        markdown_path = DebateTranscriptRenderer().save(debate)

        print("\n===== 투자 토론 완료 =====")
        print(f"토론 원본 JSON: {json_path}")
        print(f"토론 기록 Markdown: {markdown_path}")
        print("토론 원문 뷰어: view_debate.bat")
        print("최종 투자 판단은 토론 내용과 근거를 확인한 사용자가 내립니다.")
        return 0
    except Exception as error:
        print(f"\n오류가 발생했습니다: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
