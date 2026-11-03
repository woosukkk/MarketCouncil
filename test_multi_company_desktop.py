"""Offline multi-company Desktop selection, local save and private upload regression."""
import json
import os
import queue
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import app
from desktop.main import Desktop
# Preload real helpers so restoring sys.modules also preserves package module identities.
from tools import analysis_debate_store, company_lookup, debate_transcript_renderer


class MultiCompanyDesktopTests(unittest.TestCase):
    def test_sequential_company_choices_save_separately_and_upload_only_citations(self) -> None:
        cases = [
            ("SK하이닉스", "SK하이닉스", "000660.KS", "KOSPI"),
            ("현대차", "현대자동차", "005380.KS", "KOSPI"),
            ("NAVER", "NAVER", "035420.KS", "KOSPI"),
            ("Apple", "Apple Inc.", "AAPL", "NASDAQ"),
            ("Microsoft", "Microsoft Corporation", "MSFT", "NASDAQ"),
        ]
        desktop = Desktop.__new__(Desktop)
        for name in ("company", "key", "dart", "search", "company_choice", "root", "log", "status"):
            setattr(desktop, name, Mock())
        desktop.key.get.return_value = "offline-test-key"
        desktop.dart.get.return_value = ""
        desktop.search.get.return_value = "http://127.0.0.1:8080"
        desktop.company_choice.current.return_value = 0
        desktop.busy = False
        desktop.loaded_settings = None
        desktop.messages = queue.Queue()
        desktop.session = {"user": {"id": "synthetic-owner"}, "access_token": "synthetic-token"}
        desktop.task = Mock(side_effect=lambda work: work())
        analyzed = []
        uploaded = []

        def analyze(company: str) -> dict:
            ticker = os.environ["MARKETCOUNCIL_TICKER"]
            analyzed.append((company, ticker, os.environ.get("MARKETCOUNCIL_COMPANY")))
            return {
                "company_name": company,
                "financial_data": {"ticker": ticker},
                "rounds": [{"bull_response": {"issues": [{
                    "claim": "Synthetic claim for " + company,
                    "evidence": [{"source_id": "SRC-" + ticker, "exact_quote": "Cited " + company,
                                  "context_text": "LOCAL ONLY " + ticker}],
                }]}}],
                "evidence": {"source_documents": [{"content": "FULL DOCUMENT " + ticker}]},
            }

        def request(path: str, body: dict | None = None, token: str = "", method: str = "POST") -> list:
            self.assertEqual(token, desktop.session["access_token"])
            if method == "GET":
                self.assertTrue(path.startswith("/rest/v1/discussions?id=eq."))
                return []
            self.assertEqual((method, path), ("POST", "/rest/v1/discussions"))
            uploaded.append(body)
            return [{"id": body["id"]}]

        workflow = SimpleNamespace(DebateWorkflow=Mock(return_value=SimpleNamespace(run=Mock(side_effect=analyze))))
        metrics = SimpleNamespace(measure_analysis=Mock(side_effect=lambda company, work, target: work()))
        services = SimpleNamespace(ensure_local_services=Mock())
        original_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder).resolve() / "MarketCouncil"
            data.mkdir()
            (data / "browser-ready").touch()
            paths = []
            try:
                with patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1"}), \
                     patch("desktop.main.DATA", data), \
                     patch.object(app, "local_services", services, create=True), \
                     patch.dict(sys.modules, {"app.local_services": services,
                                              "app.debate_workflow": workflow,
                                              "tools.run_metrics": metrics}), \
                     patch.object(company_lookup, "find_companies") as lookup, \
                     patch.object(debate_transcript_renderer, "DebateTranscriptRenderer") as renderer, \
                     patch("desktop.main.messagebox.askyesno", return_value=True), \
                     patch("desktop.main.messagebox.showerror") as error, \
                     patch("desktop.main.messagebox.showinfo") as info, \
                     patch("desktop.main.subprocess.run", side_effect=AssertionError("No subprocess expected")) as process, \
                     patch("desktop.cloud.request", side_effect=request), \
                     patch("desktop.cloud.prepare_official") as prepare, \
                     patch("desktop.cloud.publish_official") as publish:
                    for index, (query, company, ticker, exchange) in enumerate(cases):
                        with self.subTest(company=company):
                            desktop.company.get.return_value = query
                            lookup.return_value = [{"name": company, "ticker": ticker, "exchange": exchange}]
                            desktop.lookup_company()
                            desktop.poll()
                            lookup.assert_called_with(query)
                            desktop.run()
                            self.assertEqual(analyzed[-1], (company, ticker, company))
                            self.assertEqual(len(uploaded), index, "Analysis alone must stay local")
                            paths.append(desktop.result_path)
                            self.assertTrue(desktop.result_path.is_relative_to(data / "results" / "analysis_debate"))
                            local = json.loads(desktop.result_path.read_text(encoding="utf-8"))
                            self.assertEqual((local["company_name"], local["financial_data"]["ticker"]), (company, ticker))
                            self.assertEqual(local["evidence"]["source_documents"][0]["content"], "FULL DOCUMENT " + ticker)
                            desktop.upload()
                            row = uploaded[-1]
                            self.assertEqual((row["company_name"], row["ticker"]), (company, ticker))
                            self.assertEqual(row["user_id"], desktop.session["user"]["id"])
                            self.assertNotIn("visibility", row)
                            self.assertNotIn("visibility", row["payload"])
                            self.assertNotIn("evidence", row["payload"])
                            citation = row["payload"]["rounds"][0]["bull_response"]["issues"][0]["evidence"][0]
                            self.assertEqual(citation["exact_quote"], "Cited " + company)
                            self.assertNotIn("context_text", citation)
                            self.assertNotIn("FULL DOCUMENT", json.dumps(row))
                            self.assertNotIn("LOCAL ONLY", json.dumps(row))
                    self.assertEqual(len(set(paths)), len(cases))
                    self.assertEqual(len({path.parent for path in paths}), len(cases))
                    self.assertEqual(len({row["id"] for row in uploaded}), len(cases))
                    for path, (_, company, ticker, _) in zip(paths, cases):
                        saved = json.loads(path.read_text(encoding="utf-8"))
                        self.assertEqual((saved["company_name"], saved["financial_data"]["ticker"]), (company, ticker))
                    self.assertEqual(services.ensure_local_services.call_count, len(cases))
                    self.assertEqual(renderer.return_value.save.call_count, len(cases))
                    self.assertEqual(metrics.measure_analysis.call_count, len(cases))
                    error.assert_not_called()
                    info.assert_not_called()
                    prepare.assert_not_called()
                    publish.assert_not_called()
                    process.assert_not_called()
            finally:
                os.chdir(original_cwd)
            self.assertIs(sys.modules['tools.analysis_debate_store'], analysis_debate_store)
            self.assertIs(sys.modules['tools.debate_transcript_renderer'], debate_transcript_renderer)


if __name__ == "__main__":
    unittest.main()
