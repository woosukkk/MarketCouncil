import unittest
from unittest.mock import MagicMock

from tools.youtube_channel_shorts import YouTubeChannelShorts


class YouTubeChannelShortsTest(unittest.TestCase):
    def test_returns_latest_three_unique_shorts(self) -> None:
        opener = MagicMock()
        response = opener.return_value.__enter__.return_value
        response.read.return_value = "".join(
            f'"reelWatchEndpoint":{{"videoId":"{video_id}"}}'
            for video_id in (
                "AAAAAAAAAAA",
                "BBBBBBBBBBB",
                "AAAAAAAAAAA",
                "CCCCCCCCCCC",
                "DDDDDDDDDDD",
            )
        ).encode()

        result = YouTubeChannelShorts(opener).latest()

        self.assertEqual(
            [item["video_id"] for item in result],
            ["AAAAAAAAAAA", "BBBBBBBBBBB", "CCCCCCCCCCC"],
        )
        self.assertTrue(all(
            item["channel_url"] == YouTubeChannelShorts.CHANNEL_URL
            for item in result
        ))
        self.assertEqual(opener.call_count, 1)
        self.assertEqual(opener.call_args.kwargs, {"timeout": 20})

    def test_rejects_page_without_shorts(self) -> None:
        opener = MagicMock()
        response = opener.return_value.__enter__.return_value
        response.read.return_value = b"no shorts"

        with self.assertRaisesRegex(RuntimeError, "Shorts 영상을 찾지 못했습니다"):
            YouTubeChannelShorts(opener).latest()


if __name__ == "__main__":
    unittest.main()
