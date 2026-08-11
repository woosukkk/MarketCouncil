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
