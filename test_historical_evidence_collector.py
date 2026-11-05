"""Historical evidence uses verified original text, not filing-list metadata."""
import copy
import unittest
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from tools.evidence_catalog import EvidenceCatalog
from tools.historical_evidence_collector import HistoricalEvidenceCollector
from test_evidence_preflight import primary_manifest


class HistoricalEvidenceTests(unittest.TestCase):
    def collector(self) -> HistoricalEvidenceCollector:
        collector=HistoricalEvidenceCollector.__new__(HistoricalEvidenceCollector)
        collector.dart=Mock()
        collector.search=SimpleNamespace(search=Mock(return_value=[]))
        collector.extractor=SimpleNamespace(extract_many=AsyncMock(return_value=([],[])))
        return collector

    def test_filing_list_metadata_never_becomes_official_body_evidence(self) -> None:
        collector=self.collector()
        collector.dart.list_history.return_value=[{"rcept_no":"20240101000001","rcept_dt":"20240101","report_nm":"사업보고서","flr_nm":"삼성전자"}]
        manifest=primary_manifest("삼성전자","005930.KS")
        for document in manifest["documents"]:document.pop("content")
        manifest.update(status="ready",ready=True)
        with patch("tools.company_evidence_collector.CompanyEvidenceCollector") as store,patch("app.evidence_preflight.evidence_base",return_value=Path("synthetic-local-cache")):
            store.return_value.load.return_value=manifest
            self.assertEqual(collector._dart_documents("삼성전자","005930.KS"),[])
        collector.dart.list_history.assert_not_called()
        store.return_value.collect.assert_not_called()

    def test_verified_original_bundle_is_reused_as_literal_dated_official_excerpts(self) -> None:
        collector=self.collector();manifest=primary_manifest("삼성전자","005930.KS")
        source_by_url={document["source_url"]:document for document in manifest["documents"]}
        with patch("tools.company_evidence_collector.CompanyEvidenceCollector") as store,patch("app.evidence_preflight.evidence_base",return_value=Path("synthetic-local-cache")):
            store.return_value.load.return_value=manifest
            documents=collector._dart_documents("삼성전자","005930.KS")
        self.assertTrue(documents)
        for document in documents:
            original=source_by_url[document["url"]]
            self.assertIn(document["content"],original["content"])
            self.assertLessEqual(len(document["content"]),2000)
            self.assertEqual(document["published_date"],original["published_at"])
            self.assertEqual((document["source_type"],document["search_focus"]),("official","official"))
        catalog=EvidenceCatalog.from_web_documents(documents)
        self.assertTrue(all(entry["source_type"]=="official" for entry in catalog))
        collector.dart.list_history.assert_not_called();store.return_value.collect.assert_not_called()

    def test_changed_local_body_or_unreadable_bundle_does_not_fall_back_to_metadata(self) -> None:
        collector=self.collector();manifest=primary_manifest("삼성전자","005930.KS")
        for document in manifest["documents"]:document["content"]="unverified replaced local bytes "*70
        with patch("tools.company_evidence_collector.CompanyEvidenceCollector") as store:
            store.return_value.load.return_value=manifest
            self.assertEqual(collector._dart_documents("삼성전자","005930.KS"),[])
            for error in (OSError("synthetic unavailable"),ValueError("synthetic invalid cache"),KeyError("synthetic missing field")):
                store.return_value.load.side_effect=error
                with self.subTest(error=type(error).__name__):
                    self.assertEqual(collector._dart_documents("삼성전자","005930.KS"),[])
        collector.dart.list_history.assert_not_called()

    def test_official_search_intent_cannot_grant_source_authority_in_history_or_catalog(self) -> None:
        collector=self.collector()
        url="https://random-blog.example/official-earnings"
        collector.search.search.side_effect=lambda *args,**kwargs:[{"url":url,"title":"Search result"}]
        document={"title":"Unverified blog report","url":url,"published_date":date.today().isoformat(),
                  "content":"A dated third-party financial report with attributable prose. "*35,
                  "search_focus":"official","source_type":"official"}
        collector.extractor.extract_many.return_value=([document],[])
        with patch.object(collector,"_dart_documents",return_value=[]):
            documents=collector.collect("삼성전자","005930.KS")
        self.assertEqual(len(documents),1)
        candidates=collector.extractor.extract_many.await_args.args[0]
        self.assertEqual(candidates[0]["search_focus"],"official")
        self.assertEqual(documents[0]["source_type"],"unknown")
        self.assertEqual(documents[0]["search_focus"],"unknown")
        self.assertEqual(EvidenceCatalog.from_web_documents(documents)[0]["source_type"],"unknown")

    def test_unverified_web_history_keeps_only_dates_inside_the_three_year_window(self) -> None:
        collector=self.collector();today=date.today()
        collector.search.search.side_effect=lambda *args,**kwargs:[{"url":"https://news.example/result"}]
        dates=[today.isoformat(),(today+timedelta(days=1)).isoformat(),(today-timedelta(days=365*3+1)).isoformat(),"unknown"]
        documents=[{"url":f"https://news.example/{index}","published_date":value,"content":"Dated report body. "*40,"search_focus":"news"} for index,value in enumerate(dates)]
        collector.extractor.extract_many.return_value=(copy.deepcopy(documents),[])
        with patch.object(collector,"_dart_documents",return_value=[]):
            collected=collector.collect("삼성전자","005930.KS")
        self.assertEqual([document["url"] for document in collected],[documents[0]["url"]])
        self.assertEqual(collected[0]["source_type"],"news")


if __name__=="__main__":unittest.main()
