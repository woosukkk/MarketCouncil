import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from tools.crawl4ai_extractor import Crawl4AIExtractor
from tools.evidence_text import clean_article_text, is_navigation_text


PARAGRAPH = "The company reported revenue of 1,234 KRW and operating margin of 12.5% for the year ended 2025-12-31."


class CrawlBodyTests(unittest.TestCase):
    def test_long_navigation_is_removed_before_the_budget(self) -> None:
        menus = "".join(f'<a href="/menu/{index}">Business</a>' for index in range(150))
        html = f"<html><body><header>{menus}</header><nav>{menus}</nav><article><h1>A headline</h1><p>{PARAGRAPH}</p></article><footer>{PARAGRAPH}</footer></body></html>"
        self.assertGreater(html.index(PARAGRAPH), 1200)
        text = Crawl4AIExtractor._body_text(SimpleNamespace(html=html, markdown=menus))
        self.assertEqual(text, PARAGRAPH)
        self.assertLessEqual(len(Crawl4AIExtractor._limit_text(text)), 1200)
        self.assertNotIn("Business", text)

    def test_inline_link_text_and_numeric_table_rows_survive(self) -> None:
        html = f'<article><p>{PARAGRAPH} The <a href="https://example.com/report">share count was 100,000 shares</a>.</p><table><tr><th>Period</th><th>Revenue KRW</th><th>Margin</th></tr><tr><td>2025</td><td>1,234</td><td>-0.5%</td></tr></table></article>'
        text = Crawl4AIExtractor._html_article_text(html)
        self.assertIn("share count was 100,000 shares", text)
        self.assertIn("Period | Revenue KRW | Margin", text)
        self.assertIn("2025 | 1,234 | -0.5%", text)
        self.assertNotIn("https://", text)

    def test_table_only_body_remains_usable(self) -> None:
        html = '<article><table><tr><th>Period</th><th>Revenue KRW</th></tr><tr><td>2025</td><td>1,234</td></tr></table></article>'
        self.assertIn("2025 | 1,234", Crawl4AIExtractor._html_article_text(html))

    def test_table_section_preserves_period_and_unit_context(self) -> None:
        html = '<article><h1>Headline</h1><h2>2025 fiscal year, unit KRW</h2><table><tr><th>Metric</th><th>Value</th></tr><tr><td>Revenue</td><td>1,234</td></tr></table></article>'
        self.assertIn('2025 fiscal year, unit KRW', Crawl4AIExtractor._html_article_text(html))
        markdown = '## 2025 fiscal year, unit KRW\nMetric | Value\nRevenue | 1,234'
        self.assertIn('2025 fiscal year, unit KRW', Crawl4AIExtractor._markdown_text(markdown))
        self.assertEqual(Crawl4AIExtractor._markdown_text('## '+PARAGRAPH), '')
        self.assertFalse(is_navigation_text('회사는 무단 복제 문제로 소프트웨어 매출이 감소했다고 설명했다.'))

    def test_fit_markdown_is_preferred_and_bad_fit_falls_back_to_raw(self) -> None:
        fit = PARAGRAPH
        raw = "An unrelated raw paragraph is deliberately long enough to be a complete article sentence."
        self.assertEqual(Crawl4AIExtractor._markdown_text(SimpleNamespace(fit_markdown=fit, raw_markdown=raw)), fit)
        self.assertEqual(Crawl4AIExtractor._markdown_text(SimpleNamespace(fit_markdown='[SkipNavigation](https://example.com/#main)', raw_markdown=raw)), raw)

    def test_navigation_and_headline_only_do_not_become_body(self) -> None:
        markdown = '# Revenue rises 30% in a long and detailed headline about the financial period\n[Home](https://example.com)\n[SkipNavigation](https://example.com/#main)\n[![logo](logo.png)](https://example.com)'
        self.assertEqual(Crawl4AIExtractor._markdown_text(markdown), "")
        self.assertEqual(Crawl4AIExtractor._html_article_text('<article><h1>'+PARAGRAPH+'</h1><a href="/">Home</a></article>'), "")

    def test_html_fragment_and_full_financial_sentence_link_are_supported(self) -> None:
        self.assertEqual(Crawl4AIExtractor._html_article_text('<p>'+PARAGRAPH+'</p>'), PARAGRAPH)
        self.assertEqual(clean_article_text('['+PARAGRAPH+'](https://example.com/report)'), PARAGRAPH)
        self.assertFalse(is_navigation_text('[매출 100억원](https://example.com/report)'))
        self.assertFalse(is_navigation_text('[매출이 증가했다.](https://example.com/report)'))

    def test_plain_markdown_removes_menus_images_and_duplicates(self) -> None:
        markdown = '![logo](logo.png)\n[Home](https://example.com)\n'+PARAGRAPH+'\n'+PARAGRAPH
        self.assertEqual(clean_article_text(markdown), PARAGRAPH)
        self.assertTrue(is_navigation_text('[](https://example.com/logo)'))
        self.assertTrue(is_navigation_text('Skip to main content'))

    def test_budget_does_not_cut_a_table_row_when_a_boundary_is_available(self) -> None:
        text = (PARAGRAPH+'\n\n')*15
        limited = Crawl4AIExtractor._limit_text(text)
        self.assertLessEqual(len(limited), 1200)
        self.assertTrue(limited.endswith('.'))


class CrawlBodyAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_empty_body_uses_explicit_snippet_fallback(self) -> None:
        result = SimpleNamespace(success=True, html='<article><h1>Headline only</h1></article>', markdown='[Home](https://example.com)', metadata={})
        crawler = SimpleNamespace(arun=AsyncMock(return_value=result))
        candidate = {'url':'https://example.com/article', 'title':'Headline only', 'snippet':PARAGRAPH}
        document, failure = await Crawl4AIExtractor()._extract_one(crawler, candidate, None, asyncio.Semaphore(1))
        self.assertEqual(document['extraction_method'], 'search_snippet_fallback')
        self.assertEqual(document['body_extraction_status'], 'snippet_only')
        self.assertEqual(document['content'], PARAGRAPH)
        self.assertIsNotNone(failure)

    async def test_fetch_failure_without_a_real_snippet_returns_no_document(self) -> None:
        crawler = SimpleNamespace(arun=AsyncMock(side_effect=RuntimeError('offline synthetic failure')))
        candidate = {'url':'https://example.com/article', 'title':PARAGRAPH, 'snippet':PARAGRAPH}
        document, failure = await Crawl4AIExtractor()._extract_one(crawler, candidate, None, asyncio.Semaphore(1))
        self.assertIsNone(document)
        self.assertIsNotNone(failure)

    async def test_pdf_snippet_is_marked_and_never_crawled(self) -> None:
        crawler = SimpleNamespace(arun=AsyncMock())
        candidate = {'url':'https://example.com/report.pdf', 'title':'Financial report', 'snippet':PARAGRAPH}
        document, failure = await Crawl4AIExtractor()._extract_one(crawler, candidate, None, asyncio.Semaphore(1))
        self.assertEqual(document['extraction_method'], 'search_snippet')
        self.assertEqual(document['body_extraction_status'], 'snippet_only')
        self.assertIsNone(failure)
        crawler.arun.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
