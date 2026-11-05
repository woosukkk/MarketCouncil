import json
import unittest
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch

from agents.sentiment_agent import SentimentAgent
from app.comparison_workflow import ComparisonWorkflow
from tools.source_collector_schema import SOURCE_COLLECTION_SCHEMA
from tools.source_collector import SourceCollector


class _UnavailableWebCollector:
    def collect(self, company_name: str, ticker: str | None = None) -> dict:
        raise RuntimeError("SearXNG 검색 요청이 모두 실패했습니다: 연결 실패")


def test_web_failure_returns_empty_evidence() -> None:
    collector = SourceCollector.__new__(SourceCollector)
    collector.web_collector = _UnavailableWebCollector()

    result = collector.collect("테스트기업", ticker="TEST")

    assert result["articles"] == []
    assert result["collection_method"] == "unavailable"
    assert result["summary"] == "웹 근거 확인 불가"
    assert "연결 실패" in result["search_failures"][0]["reason"]




def _article(document_id: str, url: str, **changes: Any) -> dict:
    return {
        "input_document_id": document_id,
        "title": "Invented title",
        "source_type": "news",
        "sentiment": "positive",
        "reason": "Collected event",
        "source": "invented publisher",
        "published_date": "2099-01-01",
        "url": url,
        "language": "en",
        "event_key": document_id,
        "is_primary_source": True,
        "credibility_score": 1.0,
        **changes,
    }


def _collector(documents: list[dict], articles: list[dict]) -> SourceCollector:
    collector = SourceCollector.__new__(SourceCollector)
    collector.web_collector = Mock()
    collector.web_collector.collect.return_value = {
        "documents": documents,
        "extraction_failures": [],
    }
    collector.client = Mock()
    collector.client.responses.create.return_value = SimpleNamespace(
        output_text=json.dumps({"articles": articles})
    )
    return collector


def test_classification_restores_source_metadata_from_original_document() -> None:
    document = {
        "title": "Original title",
        "url": "https://news.example/story?utm_source=search",
        "published_date": "2026-10-01",
        "content": "Original body",
    }
    collector = _collector([document], [_article("DOC-001", "https://news.example/story")])
    result = collector.collect("Example", "EXAMPLE")
    article = result["articles"][0]
    assert article["input_document_id"] == "DOC-001"
    assert article["title"] == "Original title"
    assert article["published_date"] == "2026-10-01"
    assert article["source"] == "news.example"
    assert article["url"] == "https://news.example/story"
    assert article["is_primary_source"] is False
    assert result["source_documents"][0]["input_document_id"] == "DOC-001"
    assert "input_document_id" not in document


def test_unknown_ids_and_mismatched_urls_cannot_enter_evidence() -> None:
    url = "https://news.example/story"
    collector = _collector([{"url": url}], [
        _article("DOC-999", url),
        _article("DOC-001", "https://invented.example/story"),
        _article("", url),
        "not an article",
    ])
    result = collector.collect("Example")
    assert result["articles"] == []
    assert result["evidence_pool"] == []
    assert result["coverage"]["analysis_count"] == 0


def test_missing_original_date_is_not_filled_by_model() -> None:
    url = "https://news.example/story"
    result = _collector([{"url": url}], [_article("DOC-001", url)]).collect("Example")
    assert result["articles"][0]["published_date"] == ""


def test_official_claim_requires_known_domain_and_constrains_confidence() -> None:
    url = "https://random-blog.example/story"
    result = _collector([{"url": url, "search_focus": "official"}], [
        _article("DOC-001", url, source_type="official")
    ]).collect("Example")
    article = result["articles"][0]
    assert article["source_type"] == "unknown"
    assert article["is_primary_source"] is False
    assert article["credibility_score"] == 0.2
    assert result["coverage"]["official"] == 0
    assert result["coverage"]["unknown"] == 1
    assert SentimentAgent._normalize(result.copy())["total_count"] == 1
    assert "unknown" in ComparisonWorkflow._build_web_context(result["articles"])


def test_fallback_ignores_search_focus_and_does_not_trust_lookalike_hosts() -> None:
    urls = [
        "https://random-blog.example/story",
        "https://sec.gov.evil.example/story",
        "https://evil.example/youtube.com/video",
    ]
    result = SourceCollector._fallback_result([
        {"url": url, "search_focus": "official", "source_type": "official"}
        for url in urls
    ])
    assert all(article["source_type"] == "unknown" for article in result["articles"])
    assert all(article["is_primary_source"] is False for article in result["articles"])
    official = SourceCollector._fallback_result([
        {"url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=123"},
        {"url": "https://www.sec.gov/Archives/edgar/data/123/filing.htm"},
    ])
    assert all(article["source_type"] == "official" for article in official["articles"])
    assert all(article["is_primary_source"] is True for article in official["articles"])


def test_failed_classifier_keeps_original_id_and_unknown_source_type() -> None:
    url = "https://random-blog.example/story"
    collector = _collector([{"url": url, "search_focus": "official"}], [])
    collector.client.responses.create.side_effect = RuntimeError("mock failure")
    with patch("tools.source_collector.time.sleep"):
        result = collector.collect("Example")
    article = result["articles"][0]
    assert collector.client.responses.create.call_count == 2
    assert article["input_document_id"] == "DOC-001"
    assert article["source_type"] == "unknown"
    assert article["is_primary_source"] is False


def test_document_ids_are_unique_across_classification_batches() -> None:
    documents = [{"url": f"https://publisher{index}.example/story"} for index in range(25)]
    collector = _collector(documents, [])
    received_ids = []

    def classify(**kwargs: Any) -> SimpleNamespace:
        batch = json.loads(kwargs["input"].split("\n\n", 1)[1])
        received_ids.extend(document["input_document_id"] for document in batch)
        articles = [_article(document["input_document_id"], document["url"]) for document in batch]
        return SimpleNamespace(output_text=json.dumps({"articles": articles}))

    collector.client.responses.create.side_effect = classify
    result = collector.collect("Example")
    assert received_ids == [f"DOC-{index:03d}" for index in range(1, 26)]
    assert len(result["evidence_pool"]) == 24
    assert result["source_documents"][-1]["input_document_id"] == "DOC-025"


def test_schema_requires_input_identity_and_accepts_unknown_type() -> None:
    item = SOURCE_COLLECTION_SCHEMA["properties"]["articles"]["items"]
    assert "input_document_id" in item["required"]
    assert "unknown" in item["properties"]["source_type"]["enum"]
    coverage = SOURCE_COLLECTION_SCHEMA["properties"]["coverage"]
    assert "unknown" in coverage["required"]


def test_fallback_event_ids_do_not_collide_across_batches() -> None:
    first = SourceCollector._fallback_result([
        {"input_document_id": "DOC-001", "url": "https://one.example/story"}
    ])["articles"][0]
    second = SourceCollector._fallback_result([
        {"input_document_id": "DOC-025", "url": "https://two.example/story"}
    ])["articles"][0]
    assert first["event_key"] != second["event_key"]


def load_tests(loader: unittest.TestLoader, tests: unittest.TestSuite, pattern: str | None) -> unittest.TestSuite:
    """Include the function-style regressions in the project's unittest command."""
    tests.addTests(unittest.FunctionTestCase(check, description=name)
                   for name, check in sorted(globals().items())
                   if name.startswith("test_") and callable(check))
    return tests
