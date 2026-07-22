from typing import Any

from openai import OpenAI

from agents.video_debate_prompt import (
    VIDEO_REBUTTAL_SYSTEM_PROMPT,
    VIDEO_SUMMARY_SYSTEM_PROMPT,
)
from config import MODEL_NAME, OPENAI_API_KEY
from tools.youtube_transcript_tool import YouTubeTranscriptTool


class VideoDebateAgent:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.transcript_tool = YouTubeTranscriptTool()

    def run(
        self,
        bull_video_url: str,
        bear_video_url: str,
    ) -> dict[str, Any]:
        print("[1] Bull 영상 자막 수집")
        bull_transcript = self.transcript_tool.fetch(bull_video_url)

        print("[2] Bear 영상 자막 수집")
        bear_transcript = self.transcript_tool.fetch(bear_video_url)

        print("[3] Bull 영상 요약")
        bull_summary = self._summarize("Bull", bull_transcript)

        print("[4] Bear 영상 요약")
        bear_summary = self._summarize("Bear", bear_transcript)

        print("[5] Bull의 Bear 반박")
        bull_rebuttal = self._rebut(
            role="Bull",
            own_summary=bull_summary,
            opponent_summary=bear_summary,
        )

        print("[6] Bear의 Bull 반박")
        bear_rebuttal = self._rebut(
            role="Bear",
            own_summary=bear_summary,
            opponent_summary=bull_summary,
        )

        return {
            "bull_video": self._transcript_export(bull_transcript),
            "bear_video": self._transcript_export(bear_transcript),
            "bull_summary": bull_summary,
            "bear_summary": bear_summary,
            "bull_rebuttal": bull_rebuttal,
            "bear_rebuttal": bear_rebuttal,
        }

    def _summarize(
        self,
        role: str,
        transcript: dict[str, Any],
    ) -> str:
        chunks = self.transcript_tool.split_text(transcript["text"])
        if len(chunks) == 1:
            return self._response(
                VIDEO_SUMMARY_SYSTEM_PROMPT,
                self._summary_input(role, chunks[0]),
                max_output_tokens=1800,
            )

        partial_summaries = []
        for index, chunk in enumerate(chunks, start=1):
            partial_summaries.append(self._response(
                VIDEO_SUMMARY_SYSTEM_PROMPT,
                (
                    f"{role} 관점 영상 자막의 {index}/{len(chunks)} 구간이다.\n\n"
                    f"{chunk}"
                ),
                max_output_tokens=900,
            ))

        return self._response(
            VIDEO_SUMMARY_SYSTEM_PROMPT,
            (
                f"다음은 {role} 영상의 구간별 요약이다. "
                "중복을 제거하고 하나의 최종 요약으로 통합해줘.\n\n"
                + "\n\n".join(partial_summaries)
            ),
            max_output_tokens=1800,
        )

    @staticmethod
    def _summary_input(role: str, transcript_text: str) -> str:
        return (
            f"다음은 {role} 관점 투자 영상의 전체 자막이다.\n\n"
            f"{transcript_text}"
        )

    def _rebut(
        self,
        role: str,
        own_summary: str,
        opponent_summary: str,
    ) -> str:
        return self._response(
            VIDEO_REBUTTAL_SYSTEM_PROMPT,
            f"""너의 역할: {role}

[자신의 영상 요약]
{own_summary}

[상대 영상 요약]
{opponent_summary}

자신의 영상 논거를 사용해 상대 요약의 핵심 주장을 반박해줘.""",
            max_output_tokens=1600,
        )

    def _response(
        self,
        instructions: str,
        input_text: str,
        max_output_tokens: int,
    ) -> str:
        try:
            response = self.client.responses.create(
                model=MODEL_NAME,
                instructions=instructions,
                input=input_text,
                max_output_tokens=max_output_tokens,
            )
        except Exception as error:
            raise RuntimeError("영상 토론 LLM 호출에 실패했습니다.") from error
        return response.output_text

    @staticmethod
    def _transcript_export(transcript: dict[str, Any]) -> dict[str, Any]:
        return {
            "video_id": transcript["video_id"],
            "video_url": transcript["video_url"],
            "language": transcript["language"],
            "language_code": transcript["language_code"],
            "is_generated": transcript["is_generated"],
            "segment_count": len(transcript["segments"]),
            "segments": transcript["segments"],
        }
