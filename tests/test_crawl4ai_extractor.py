import asyncio
import unittest

from tools.crawl4ai_extractor import Crawl4AIExtractor


class _FailedCrawler:
    async def arun(self, url: str, config: object) -> object:
        return type(
            "FailedResult",
            (),
            {"success": False, "error_message": "crawl failed"},
        )()


class Crawl4AIExtractorTest(unittest.TestCase):
    def test_agent_reach_is_used_after_crawl_failure(self) -> None:
        extractor = Crawl4AIExtractor()
        extractor._read_with_agent_reach = lambda url: "fallback body"

        document, failure = asyncio.run(extractor._extract_one(
            _FailedCrawler(),
            {"url": "https://example.com/article", "title": "Example"},
            object(),
            asyncio.Semaphore(1),
        ))

        self.assertIsNone(failure)
        self.assertIsNotNone(document)
        self.assertEqual(document["content"], "fallback body")
        self.assertEqual(
            document["extraction_method"],
            "agent_reach_jina",
        )


if __name__ == "__main__":
    unittest.main()
