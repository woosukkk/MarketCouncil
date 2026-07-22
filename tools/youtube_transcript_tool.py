import re
from typing import Any
from urllib.parse import parse_qs, urlsplit

from youtube_transcript_api import YouTubeTranscriptApi


class YouTubeTranscriptTool:
    PREFERRED_LANGUAGES = ("ko", "ko-KR", "en", "en-US")

    def __init__(self) -> None:
        self.api = YouTubeTranscriptApi()

    def fetch(self, video_url: str) -> dict[str, Any]:
        video_id = self.extract_video_id(video_url)

        try:
            transcript_list = self.api.list(video_id)
            transcript = self._select_transcript(transcript_list)
            fetched = transcript.fetch(preserve_formatting=False)
        except Exception as error:
            raise RuntimeError(
                "YouTube 자막을 가져오지 못했습니다. "
                "자막이 비활성화됐거나 YouTube가 접근을 제한했을 수 있습니다."
            ) from error

        segments = [
            {
                "start": float(snippet.start),
                "duration": float(snippet.duration),
                "text": snippet.text.strip(),
            }
            for snippet in fetched
            if snippet.text.strip()
        ]

        if not segments:
            raise ValueError("영상에서 사용할 수 있는 자막 문장을 찾지 못했습니다.")

        return {
            "video_id": video_id,
            "video_url": video_url,
            "language": transcript.language,
            "language_code": transcript.language_code,
            "is_generated": transcript.is_generated,
            "segments": segments,
            "text": self.format_segments(segments),
        }

    @staticmethod
    def extract_video_id(video_url: str) -> str:
        value = video_url.strip()
        if re.fullmatch(r"[0-9A-Za-z_-]{11}", value):
            return value

        parts = urlsplit(value)
        hostname = (parts.hostname or "").lower()

        if hostname in {"youtu.be", "www.youtu.be"}:
            video_id = parts.path.strip("/").split("/")[0]
        elif hostname in {
            "youtube.com",
            "www.youtube.com",
            "m.youtube.com",
        }:
            if parts.path == "/watch":
                video_id = parse_qs(parts.query).get("v", [""])[0]
            elif parts.path.startswith(("/shorts/", "/embed/", "/live/")):
                video_id = parts.path.strip("/").split("/")[1]
            else:
                video_id = ""
        else:
            video_id = ""

        if not re.fullmatch(r"[0-9A-Za-z_-]{11}", video_id):
            raise ValueError("올바른 YouTube 영상 URL 또는 ID가 아닙니다.")
        return video_id

    @classmethod
    def _select_transcript(cls, transcript_list):
        try:
            return transcript_list.find_manually_created_transcript(
                cls.PREFERRED_LANGUAGES
            )
        except Exception:
            pass

        try:
            return transcript_list.find_generated_transcript(
                cls.PREFERRED_LANGUAGES
            )
        except Exception:
            pass

        try:
            return next(iter(transcript_list))
        except StopIteration as error:
            raise ValueError("사용할 수 있는 자막 트랙이 없습니다.") from error

    @classmethod
    def format_segments(
        cls,
        segments: list[dict[str, Any]],
    ) -> str:
        return "\n".join(
            f"[{cls.format_timestamp(segment['start'])}] {segment['text']}"
            for segment in segments
        )

    @staticmethod
    def format_timestamp(seconds: float) -> str:
        total_seconds = max(0, int(seconds))
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    @staticmethod
    def split_text(
        transcript_text: str,
        max_chars: int = 24000,
    ) -> list[str]:
        lines = transcript_text.splitlines()
        chunks: list[str] = []
        current: list[str] = []
        current_length = 0

        for line in lines:
            line_length = len(line) + 1
            if current and current_length + line_length > max_chars:
                chunks.append("\n".join(current))
                current = []
                current_length = 0
            current.append(line)
            current_length += line_length

        if current:
            chunks.append("\n".join(current))
        return chunks
