import re
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen


class YouTubeChannelShorts:
    CHANNEL_URL = (
        "https://www.youtube.com/"
        "@%EA%B9%80%EB%8B%A8%ED%85%8C/shorts"
    )
    _VIDEO_PATTERNS = (
        re.compile(r'"reelWatchEndpoint":\{"videoId":"([\w-]{11})"'),
        re.compile(r'\\?/shorts/([\w-]{11})'),
    )

    def __init__(self, opener=urlopen) -> None:
        self.opener = opener

    def latest(self, limit: int = 3) -> list[dict[str, Any]]:
        try:
            request = Request(
                self.CHANNEL_URL,
                headers={
                    "User-Agent": "Mozilla/5.0 MarketCouncil/1.0",
                    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
                },
            )
            with self.opener(request, timeout=20) as response:
                page = response.read().decode("utf-8", errors="replace")
        except (OSError, URLError) as error:
            raise RuntimeError("김단테 Shorts 목록을 가져오지 못했습니다.") from error

        video_ids: list[str] = []
        for pattern in self._VIDEO_PATTERNS:
            for video_id in pattern.findall(page):
                if video_id not in video_ids:
                    video_ids.append(video_id)
                if len(video_ids) == limit:
                    return self._items(video_ids)

        if not video_ids:
            raise RuntimeError("김단테 채널에서 Shorts 영상을 찾지 못했습니다.")
        return self._items(video_ids[:limit])

    @classmethod
    def _items(cls, video_ids: list[str]) -> list[dict[str, Any]]:
        return [
            {
                "rank": rank,
                "video_id": video_id,
                "video_url": f"https://www.youtube.com/shorts/{video_id}",
                    "channel_url": cls.CHANNEL_URL,
            }
            for rank, video_id in enumerate(video_ids, start=1)
        ]
