import json
from typing import Any

from openai import OpenAI

from agents.video_debate_prompt import (
    VIDEO_SUMMARY_SYSTEM_PROMPT,
)
from agents.video_topic_prompt import VIDEO_TOPIC_SYSTEM_PROMPT
from config import MODEL_NAME, OPENAI_API_KEY
from tools.youtube_channel_shorts import YouTubeChannelShorts
from tools.youtube_transcript_tool import YouTubeTranscriptTool


TOPIC_SCHEMA = {
    "type": "object",
    "properties": {
        "topics": {
            "type": "array",
            "maxItems": 6,
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "claim": {"type": "string"},
                    "verification_question": {"type": "string"},
                    "classification": {
                        "type": "string",
                        "enum": ["영상 발화자 가설"],
                    },
                    "source_video_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": [
                    "title",
                    "claim",
                    "verification_question",
                    "classification",
                    "source_video_ids",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["topics"],
    "additionalProperties": False,
}


class VideoDebateAgent:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.transcript_tool = YouTubeTranscriptTool()
        self.shorts_tool = YouTubeChannelShorts()

    def run_latest_short_topics(self, company_name: str) -> dict[str, Any]:
        shorts = self.shorts_tool.latest(limit=3)
        transcripts: list[dict[str, Any]] = []
        skipped: list[dict[str, str]] = []

        for short in shorts:
            try:
                transcript = self.transcript_tool.fetch(short["video_url"])
                transcripts.append({
                    **short,
                    "language": transcript["language"],
                    "is_generated": transcript["is_generated"],
                    "text": transcript["text"],
                })
            except (RuntimeError, ValueError) as error:
                skipped.append({
                    "video_id": short["video_id"],
                    "reason": str(error),
                })

        topics = self._extract_topics(company_name, transcripts) if transcripts else []
        return {
            "channel_url": YouTubeChannelShorts.CHANNEL_URL,
            "requested_count": 3,
            "videos": [
                {key: value for key, value in transcript.items() if key != "text"}
                for transcript in transcripts
            ],
            "skipped": skipped,
            "topics": topics,
        }

    def _extract_topics(
        self,
        company_name: str,
        transcripts: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        payload = {
            "company_name": company_name,
            "channel_url": YouTubeChannelShorts.CHANNEL_URL,
            "shorts": transcripts,
        }
        try:
            response = self.client.responses.create(
                model=MODEL_NAME,
                instructions=VIDEO_TOPIC_SYSTEM_PROMPT,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "shorts_debate_topics",
                        "strict": True,
                        "schema": TOPIC_SCHEMA,
                    }
                },
                input=json.dumps(payload, ensure_ascii=False, default=str),
                reasoning={"effort": "minimal"},
                max_output_tokens=1800,
            )
            result = json.loads(response.output_text)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise RuntimeError("Shorts 토론 주제 응답이 올바르지 않습니다.") from error
        except Exception as error:
            raise RuntimeError("Shorts 토론 주제 추출에 실패했습니다.") from error
        return result["topics"]

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

        return {
            "bull_video": self._transcript_export(bull_transcript),
            "bear_video": self._transcript_export(bear_transcript),
            "bull_summary": bull_summary,
            "bear_summary": bear_summary,
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
            raise RuntimeError("영상 요약 LLM 호출에 실패했습니다.") from error
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
