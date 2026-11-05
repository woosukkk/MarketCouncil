from tools.historical_evidence_collector import HistoricalEvidenceCollector


class FakeDart:
    def list_history(self, company_name: str, ticker: str) -> list[dict[str, str]]:
        return [{
            "rcept_no": "20240101000001",
            "rcept_dt": "20240101",
            "report_nm": "사업보고서",
            "flr_nm": company_name,
        }]


def test_dart_history_becomes_dated_source_document() -> None:
    collector = HistoricalEvidenceCollector.__new__(HistoricalEvidenceCollector)
    collector.dart = FakeDart()

    documents = collector._dart_documents("테스트", "000001.KS")

    assert documents[0]["published_date"] == "2024-01-01"
    assert documents[0]["search_focus"] == "official"
    assert "20240101000001" in documents[0]["url"]
