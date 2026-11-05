"""Official filing cache checks use synthetic bodies and mocked provider calls."""
import hashlib
import io
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

from tools import company_evidence_collector as evidence
from tools.dart_collector import DartCollector
from tools.sec_edgar_collector import SecEdgarCollector


def archive(content: bytes, name: str = "report.xml") -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as stream:
        stream.writestr(name, content)
    return output.getvalue()


BODY = ("Samsung Electronics 삼성전자 annual revenue financial statements. " * 50).encode()


class CompanyEvidenceCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.collector = evidence.CompanyEvidenceCollector(self.base / "cache")

    def dart_collection(self, owner: DartCollector, company: str, ticker: str, limit: int, periodic_only: bool) -> dict:
        self.assertTrue(periodic_only)
        self.assertEqual(ticker, "005930.KS")
        directory = owner.base_dir / "dart" / company
        directory.mkdir(parents=True, exist_ok=True)
        for identifier, form, published in [
            ("20260310000001", "사업보고서 (2025.12)", "20260310"),
            ("20260910000002", "반기보고서 (2026.06)", "20260910"),
        ]:
            original = directory / (identifier + ".zip")
            original.write_bytes(archive(b"<script>secret script</script><nav>navigation only</nav><p>" + BODY + b"</p>"))
            metadata = {"provider": "open_dart", "identity_verified": True, "company": company,
                        "ticker": "005930", "corp_code": "00126380", "filing_id": identifier,
                        "form_type": form, "filed_at": published,
                        "source_url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=" + identifier,
                        "original_path": str(original)}
            (directory / (identifier + ".metadata.json")).write_text(json.dumps(metadata), encoding="utf-8")
        return {"issuer_id": "00126380", "failed": [], "requested_ids": ["20260310000001", "20260910000002"], "latest_required_ids": ["20260310000001", "20260910000002"]}

    def collect(self) -> dict:
        with patch.dict(os.environ, {"DART_API_KEY": "synthetic-only"}), \
             patch.object(DartCollector, "collect", autospec=True, side_effect=self.dart_collection):
            return self.collector.collect("삼성전자", "005930.KS")

    def test_collect_load_rechecks_real_files_and_json_never_contains_body(self) -> None:
        manifest = self.collect()
        self.assertEqual(manifest["failures"], [])
        self.assertEqual([document["document_type"] for document in manifest["documents"]], ["annual", "interim"])
        self.assertEqual([document["report_date"] for document in manifest["documents"]], ["2025-12-31", "2026-06-30"])
        for document in manifest["documents"]:
            self.assertNotIn("secret script", document["content"])
            self.assertNotIn("navigation only", document["content"])
            self.assertEqual(document["content_hash"], hashlib.sha256(document["content"].encode()).hexdigest())
        cache_path = self.base / "cache/005930.KS/manifest.json"
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        self.assertNotIn("content", cache["documents"][0])
        self.assertFalse(Path(cache["documents"][0]["text_path"]).is_absolute())
        cache["documents"][0]["content"] = "invented inline content"
        cache_path.write_text(json.dumps(cache), encoding="utf-8")
        loaded = self.collector.load("삼성전자", "005930.KS")
        self.assertEqual(loaded["documents"][0]["content"], manifest["documents"][0]["content"])
        self.assertNotIn("invented inline", loaded["documents"][0]["content"])

    def test_changed_original_text_or_outside_path_never_becomes_ready_input(self) -> None:
        for changed, code in [("original", "original_hash_mismatch"), ("text", "text_hash_mismatch"), ("outside", "cache_path_outside_company_or_missing")]:
            with self.subTest(changed=changed):
                manifest = self.collect()
                document = manifest["documents"][0]
                cache_path = self.base / "cache/005930.KS/manifest.json"
                if changed == "outside":
                    outside = self.base / "outside.txt"
                    outside.write_text(document["content"], encoding="utf-8")
                    cache = json.loads(cache_path.read_text(encoding="utf-8"))
                    cache["documents"][0]["text_path"] = str(outside)
                    cache_path.write_text(json.dumps(cache), encoding="utf-8")
                else:
                    target = Path(document["original_path"] if changed == "original" else document["text_path"])
                    target.write_bytes(target.read_bytes() + b"tampered")
                loaded = self.collector.load("삼성전자", "005930.KS")
                self.assertEqual(len(loaded["documents"]), 1)
                self.assertIn(code, [failure["code"] for failure in loaded["failures"]])

    def test_invalid_merge_does_not_replace_valid_manifest(self) -> None:
        manifest = self.collect()
        path = self.base / "cache/005930.KS/manifest.json"
        before = path.read_bytes()
        manifest["documents"][0]["ticker"] = "000660.KS"
        with self.assertRaisesRegex(ValueError, "company_identity_mismatch"):
            self.collector.save(manifest)
        self.assertEqual(path.read_bytes(), before)

    def test_missing_original_and_unverified_metadata_are_not_documents(self) -> None:
        self.collect()
        metadata_paths = list((self.base / "cache/005930.KS/raw").rglob("*.metadata.json"))
        for index, path in enumerate(metadata_paths):
            metadata = json.loads(path.read_text())
            if index:
                Path(metadata["original_path"]).unlink()
            else:
                metadata["identity_verified"] = False
                path.write_text(json.dumps(metadata))
        with patch.dict(os.environ, {"DART_API_KEY": "synthetic-only"}), \
             patch.object(DartCollector, "collect", return_value={"issuer_id": "00126380", "failed": [], "requested_ids": ["20260310000001", "20260910000002"], "latest_required_ids": ["20260310000001", "20260910000002"]}):
            manifest = self.collector.collect("삼성전자", "005930.KS")
        self.assertEqual(manifest["documents"], [])
        self.assertEqual(len(manifest["failures"]), 2)

    def test_absent_credentials_does_not_call_provider_or_invent_evidence(self) -> None:
        with patch.dict(os.environ, {"DART_API_KEY": ""}), patch.object(DartCollector, "collect") as collect:
            result = self.collector.collect("삼성전자", "005930.KS")
        collect.assert_not_called()
        self.assertEqual(result["documents"], [])
        self.assertTrue(result["failures"])

    def test_sec_issuer_and_source_are_verified_again_on_load(self) -> None:
        root = self.base / "cache/AAPL"
        root.mkdir(parents=True)
        original, text_path = root / "report.html", root / "report.txt"
        original.write_bytes(b"<p>" + BODY + b"</p>")
        text = evidence.extract_official_text(original)
        text_path.write_text(text, encoding="utf-8")
        document = {"document_id": "0000320193-26-000001", "company_name": "Apple Inc.", "ticker": "AAPL",
                    "provider": "sec_edgar", "issuer_id": "0000320193", "document_type": "annual", "source_type": "official",
                    "published_at": "2026-10-30", "report_date": "2026-09-30", "identity_verified": True,
                    "source_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019326000001/report.html",
                    "original_path": str(original), "text_path": str(text_path),
                    "original_hash": hashlib.sha256(original.read_bytes()).hexdigest(), "content_hash": hashlib.sha256(text.encode()).hexdigest()}
        manifest = {"company_name": "Apple Inc.", "ticker": "AAPL", "issuer_id": "0000320193", "documents": [document], "failures": []}
        self.collector.save(manifest)
        self.assertEqual(len(self.collector.load("Apple", "AAPL")["documents"]), 1)
        document["issuer_id"] = "0000789019"
        with self.assertRaisesRegex(ValueError, "issuer_identity_mismatch"):
            self.collector.save(manifest)

    def test_six_company_caches_keep_the_selected_issuer_and_company_separate(self) -> None:
        from tools.company_profiles import PROFILES

        def collect(owner: object, company: str, ticker: str, limit: int, periodic_only: bool) -> dict:
            profile = next(row for row in PROFILES if row["ticker"] == ticker)
            korean = profile["market"] == "kr"
            issuer = "00000001" if korean else profile["sec_cik"]
            provider = "open_dart" if korean else "sec_edgar"
            directory = owner.base_dir / ("dart" if korean else "sec") / owner._safe_name(company)
            directory.mkdir(parents=True, exist_ok=True)
            requested = []
            for index, (kind, date_value, period) in enumerate([
                ("annual", "2026-03-10", "2025-12-31"), ("interim", "2026-09-10", "2026-06-30")
            ], 1):
                identifier = date_value.replace("-", "") + f"00000{index}" if korean else f"{issuer}-26-00000{index}"
                requested.append(identifier)
                original = directory / (identifier + (".zip" if korean else ".htm"))
                body = ("<p>" + (company + " financial statement revenue. ") * 100 + "</p>").encode()
                original.write_bytes(archive(body) if korean else body)
                metadata = {"provider": provider, "company": company, "ticker": ticker.split(".")[0] if korean else ticker,
                            "identity_verified": True, "corp_code" if korean else "cik": issuer, "filing_id": identifier,
                            "form_type": ("사업보고서 (2025.12)" if kind == "annual" else "반기보고서 (2026.06)") if korean else ("10-K" if kind == "annual" else "10-Q"),
                            "filed_at": date_value, "report_date": period, "original_path": str(original),
                            "source_url": ("https://dart.fss.or.kr/dsaf001/main.do?rcpNo=" + identifier) if korean else
                                          f"https://www.sec.gov/Archives/edgar/data/{int(issuer)}/{identifier.replace('-', '')}/{original.name}"}
                (directory / (identifier + ".metadata.json")).write_text(json.dumps(metadata), encoding="utf-8")
            return {"issuer_id": issuer, "failed": [], "requested_ids": requested, "latest_required_ids": requested}

        with patch.dict(os.environ, {"DART_API_KEY": "synthetic-only", "SEC_USER_AGENT": "Synthetic <test@example.invalid>"}), \
             patch.object(DartCollector, "collect", autospec=True, side_effect=collect), \
             patch.object(SecEdgarCollector, "collect", autospec=True, side_effect=collect):
            for profile in PROFILES:
                with self.subTest(ticker=profile["ticker"]):
                    self.collector.collect(profile["company_name"], profile["ticker"])
                    loaded = self.collector.load(profile["company_name"], profile["ticker"])
                    self.assertEqual(loaded["failures"], [])
                    self.assertEqual(len(loaded["documents"]), 2)
                    for document in loaded["documents"]:
                        self.assertEqual((document["company_name"], document["ticker"]), (profile["company_name"], profile["ticker"]))
                        self.assertIn(profile["company_name"], document["content"])
                        self.assertTrue(Path(document["original_path"]).is_relative_to(self.base / "cache" / profile["ticker"]))


class OfficialTextTests(unittest.TestCase):
    def test_zip_expansion_member_limit_and_block_page_checks(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "report.zip"
            path.write_bytes(archive(b"A" * 2000))
            with patch.object(evidence, "MAX_ZIP_BYTES", 1000):
                with self.assertRaisesRegex(ValueError, "archive_limit_exceeded"):
                    evidence.extract_official_text(path)
            with zipfile.ZipFile(path, "w") as zipped:
                for index in range(3):
                    zipped.writestr(str(index) + ".xml", BODY)
            with patch.object(evidence, "MAX_ZIP_MEMBERS", 2):
                with self.assertRaisesRegex(ValueError, "archive_limit_exceeded"):
                    evidence.extract_official_text(path)
            path = Path(folder) / "denied.html"
            path.write_text("Access denied " + "support " * 200)
            with self.assertRaisesRegex(ValueError, "blocked_response_body"):
                evidence.extract_official_text(path)
            path.write_text("<nav>" + "navigation " * 200 + "</nav>")
            with self.assertRaisesRegex(ValueError, "invalid_text_length"):
                evidence.extract_official_text(path)


class PeriodicFilingSelectionTests(unittest.TestCase):
    def test_dart_periodic_query_checks_issuer_and_disallows_name_fallback(self) -> None:
        collector = DartCollector("synthetic-only", Path("unused"))
        response = Mock()
        response.json.return_value = {"status": "000", "list": [{"corp_code": "00126380"}], "total_page": 1}
        with patch.object(collector, "_get", return_value=response) as get:
            collector._list_filings("00126380", 5, 365, periodic_only=True)
            self.assertEqual(get.call_args.kwargs["params"]["pblntf_ty"], "A")
        response.json.return_value["list"][0]["corp_code"] = "other"
        with patch.object(collector, "_get", return_value=response):
            with self.assertRaisesRegex(RuntimeError, "식별자"):
                collector._list_filings("00126380", 5, 365, periodic_only=True)
        response = Mock(content=archive(b"<result><list><corp_code>00126380</corp_code><corp_name>Samsung</corp_name><stock_code>999999</stock_code></list></result>", "CORPCODE.xml"))
        with patch.object(collector, "_get", return_value=response):
            with self.assertRaises(ValueError):
                collector._resolve_corp_code("Samsung", "005930", strict_stock=True)
            self.assertEqual(collector._resolve_corp_code("Samsung", "005930"), "00126380")

    def test_dart_selection_reserves_annual_and_latest_interim(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            collector = DartCollector("synthetic-only", Path(folder))
            rows = [{"rcept_no": f"202600000000{index:02d}", "report_nm": title, "rcept_dt": "20260910"}
                    for index, title in enumerate(["반기보고서 (2026.06)", "분기보고서 (2026.03)", "사업보고서 (2025.12)"])]
            with patch.object(collector, "_resolve_corp_code", return_value="00126380") as identity, \
                 patch.object(collector, "_list_filings", return_value=rows), \
                 patch.object(collector, "_download_original", return_value=archive(BODY)) as download:
                result = collector.collect("삼성전자", "005930.KS", limit=2, periodic_only=True)
                identity.assert_called_once_with("삼성전자", "005930", strict_stock=True)
                repeated = collector.collect("삼성전자", "005930.KS", limit=2, periodic_only=True)
            self.assertEqual(result["requested_ids"], [rows[2]["rcept_no"], rows[0]["rcept_no"]])
            self.assertEqual(result["latest_required_ids"], result["requested_ids"])
            self.assertEqual(repeated["requested_ids"], result["requested_ids"])
            self.assertEqual(download.call_count, 2)
            self.assertEqual(len(repeated["skipped"]), 2)
            self.assertEqual(repeated["downloaded"], [])
            self.assertEqual([row["form_type"] for row in result["downloaded"]], ["사업보고서 (2025.12)", "반기보고서 (2026.06)"])

    def test_sec_cached_originals_are_not_downloaded_again(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            collector = SecEdgarCollector("Synthetic test <test@example.invalid>", Path(folder))
            rows = [{"accession_number": f"0000320193-26-00000{index}", "form": form,
                     "primary_document": "report.htm", "filing_date": "2026-10-30", "report_date": "2026-09-30"}
                    for index, form in enumerate(["10-K", "10-Q"])]
            with patch.object(collector, "_resolve_cik", return_value="0000320193"), \
                 patch.object(collector, "_list_filings", return_value=rows), \
                 patch.object(collector, "_get", return_value=Mock(content=b"<p>" + BODY + b"</p>")) as download:
                result = collector.collect("Apple Inc.", "AAPL", limit=2, periodic_only=True)
                repeated = collector.collect("Apple Inc.", "AAPL", limit=2, periodic_only=True)
            self.assertEqual(download.call_count, 2)
            self.assertEqual(len(repeated["skipped"]), 2)
            self.assertEqual(repeated["downloaded"], [])
            self.assertEqual(result["issuer_id"], "0000320193")
            self.assertEqual(result["requested_ids"], [row["accession_number"] for row in rows])
            self.assertEqual(repeated["requested_ids"], result["requested_ids"])
            self.assertEqual(result["latest_required_ids"], [rows[0]["accession_number"]])

    def test_sec_periodic_reserves_annual_instead_of_only_recent_quarters(self) -> None:
        collector = SecEdgarCollector("Synthetic test <test@example.invalid>", Path("unused"))
        rows = {"cik": 320193, "filings": {"recent": {
            "form": ["8-K", "10-Q", "10-Q", "10-K"],
            "accessionNumber": ["a", "b", "c", "d"], "filingDate": ["2026-10-30"] * 4,
            "reportDate": ["2026-09-30"] * 4, "primaryDocument": ["document.htm"] * 4}}}
        with patch.object(collector, "_get", return_value=Mock(json=Mock(return_value=rows))):
            self.assertEqual([row["form"] for row in collector._list_filings("0000320193", 2, periodic_only=True)], ["10-K", "10-Q"])
            self.assertEqual([row["form"] for row in collector._list_filings("0000320193", 2)], ["8-K", "10-Q"])
            rows["cik"] = 789019
            with self.assertRaisesRegex(RuntimeError, "식별자"):
                collector._list_filings("0000320193", 2, periodic_only=True)


class LatestPrimarySelectionTests(unittest.TestCase):
    setUp = CompanyEvidenceCacheTests.setUp
    collect = CompanyEvidenceCacheTests.collect
    dart_collection = CompanyEvidenceCacheTests.dart_collection

    def selection(self, requested: list[str], required: list[str] | None = None) -> dict:
        return {"issuer_id": "00126380", "failed": [], "requested_ids": requested,
                "latest_required_ids": requested if required is None else required}

    def current(self, result: dict) -> dict:
        with patch.dict(os.environ, {"DART_API_KEY": "synthetic-only"}), patch.object(DartCollector, "collect", return_value=result):
            return self.collector.collect("삼성전자", "005930.KS")

    def new_annual(self) -> tuple[str, Path, Path, dict]:
        old = self.base / "cache/005930.KS/raw/dart/삼성전자/20260310000001.metadata.json"
        metadata = json.loads(old.read_text(encoding="utf-8"))
        identifier = "20261030000003"
        original = old.parent / (identifier + ".zip")
        metadata.update(filing_id=identifier, filed_at="20261030", form_type="사업보고서 (2026.09)",
                        source_url="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=" + identifier,
                        original_path=str(original))
        original.write_bytes(archive(b"<p>" + BODY + b" new annual financial body</p>"))
        path = old.parent / (identifier + ".metadata.json")
        path.write_text(json.dumps(metadata), encoding="utf-8")
        return identifier, original, path, metadata

    def test_latest_required_body_identity_and_period_failure_cannot_use_older_raw(self) -> None:
        for failure in ("body", "identity", "period", "filing_id"):
            with self.subTest(failure=failure):
                self.collect()
                identifier, original, path, metadata = self.new_annual()
                if failure == "body":original.write_bytes(archive(b"<p>short</p>"))
                elif failure == "identity":metadata["identity_verified"] = False
                elif failure == "period":metadata["form_type"] = "사업보고서"
                else:metadata["filing_id"] = "20260310000001"
                path.write_text(json.dumps(metadata), encoding="utf-8")
                result = self.current(self.selection([identifier, "20260910000002", "20260310000001"], [identifier, "20260910000002"]))
                self.assertTrue(result["latest_primary_failed"])
                self.assertIn("20260310000001", [doc["document_id"] for doc in result["documents"]])
                self.assertNotIn(identifier, [doc["document_id"] for doc in result["documents"]])
                self.assertTrue(self.collector.load("삼성전자", "005930.KS")["latest_primary_failed"])

    def test_latest_pdf_parser_failure_is_recorded_without_private_detail_and_persisted(self) -> None:
        self.collect()
        identifier, original, metadata_path, metadata = self.new_annual()
        pdf = original.with_suffix(".pdf")
        pdf.write_bytes(b"%PDF-1.7\nprivate corrupt pdf content")
        metadata["original_path"] = str(pdf)
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
        result = self.current(self.selection([identifier, "20260910000002", "20260310000001"], [identifier, "20260910000002"]))
        self.assertTrue(result["latest_primary_failed"])
        self.assertTrue(any(row["stage"] == "validation" and row["document_id"] == identifier for row in result["failures"]))
        self.assertNotIn("private corrupt pdf content", repr(result["failures"]))
        self.assertTrue(self.collector.load("삼성전자", "005930.KS")["latest_primary_failed"])

    def test_only_requested_current_ids_are_read_and_unrelated_corrupt_raw_is_ignored(self) -> None:
        self.collect()
        identifier, _, _, _ = self.new_annual()
        raw = self.base / "cache/005930.KS/raw/dart/삼성전자"
        (raw / "19990101000001.metadata.json").write_text("PRIVATE BAD OLD METADATA", encoding="utf-8")
        result = self.current(self.selection([identifier, "20260910000002"]))
        self.assertFalse(result["latest_primary_failed"])
        self.assertEqual(result["failures"], [])
        self.assertEqual({doc["document_id"] for doc in result["documents"]}, {identifier, "20260910000002"})
        self.assertFalse(self.collector.load("삼성전자", "005930.KS")["latest_primary_failed"])

    def test_missing_optional_requested_document_does_not_block_required_success(self) -> None:
        self.collect()
        result = self.selection(["20260310000001", "20260910000002", "20260610000004"], ["20260310000001", "20260910000002"])
        result["failed"] = [{"id": "20260610000004", "reason": "private provider error"}]
        manifest = self.current(result)
        self.assertFalse(manifest["latest_primary_failed"])
        self.assertTrue(manifest["failures"])
        self.assertFalse(self.collector.load("삼성전자", "005930.KS")["latest_primary_failed"])

    def test_query_failure_invalidates_and_persists_previously_valid_cache(self) -> None:
        self.assertFalse(self.collect()["latest_primary_failed"])
        with patch.dict(os.environ, {"DART_API_KEY": "synthetic-only"}), patch.object(DartCollector, "collect", side_effect=RuntimeError("private provider response")):
            result = self.collector.collect("삼성전자", "005930.KS")
        self.assertTrue(result["latest_primary_failed"])
        self.assertEqual(result["requested_ids"], [])
        self.assertEqual(result["failures"][-1], {"stage": "collection", "code": "source_unavailable"})
        self.assertNotIn("private provider response", repr(result))
        self.assertTrue(self.collector.load("삼성전자", "005930.KS")["latest_primary_failed"])

    def test_missing_or_malformed_selection_never_falls_back_to_old_raw(self) -> None:
        self.collect()
        variants = [[], None, {"issuer_id": "00126380", "failed": []}, self.selection(["../unsafe"]),
                    self.selection(["20260310000001"], ["20260910000002"]), self.selection([])]
        for selected in variants:
            with self.subTest(selected=selected):
                self.assertTrue(self.current(selected)["latest_primary_failed"])
                self.assertTrue(self.collector.load("삼성전자", "005930.KS")["latest_primary_failed"])

    def test_rehydration_rechecks_latest_id_even_with_older_same_type_present(self) -> None:
        self.collect()
        identifier, original, _, _ = self.new_annual()
        result = self.current(self.selection([identifier, "20260910000002", "20260310000001"], [identifier, "20260910000002"]))
        self.assertFalse(result["latest_primary_failed"])
        original.write_bytes(original.read_bytes() + b"changed")
        loaded = self.collector.load("삼성전자", "005930.KS")
        self.assertTrue(loaded["latest_primary_failed"])
        self.assertIn("20260310000001", [doc["document_id"] for doc in loaded["documents"]])

    def test_gate_rejected_body_cannot_satisfy_latest_required_id(self) -> None:
        self.collect()
        identifier, original, _, _ = self.new_annual()
        # More than 1,000 characters but too little actual evidence for the gate.
        original.write_bytes(archive(("<p>A" + " " * 2500 + "B</p>").encode()))
        result = self.current(self.selection([identifier, "20260910000002", "20260310000001"], [identifier, "20260910000002"]))
        self.assertTrue(result["latest_primary_failed"])


class AnnualReplacementSelectionTests(unittest.TestCase):
    def test_newer_dart_annual_does_not_require_preceding_interim(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            collector = DartCollector("synthetic-only", Path(folder))
            rows = [{"rcept_no": "20261030000001", "report_nm": "사업보고서 (2026.09)", "rcept_dt": "20261030"},
                    {"rcept_no": "20260910000002", "report_nm": "반기보고서 (2026.06)", "rcept_dt": "20260910"}]
            with patch.object(collector, "_resolve_corp_code", return_value="00126380"), patch.object(collector, "_list_filings", return_value=rows), patch.object(collector, "_download_original", return_value=archive(BODY)):
                result = collector.collect("삼성전자", "005930.KS", 2, periodic_only=True)
            self.assertEqual(result["requested_ids"], [row["rcept_no"] for row in rows])
            self.assertEqual(result["latest_required_ids"], [rows[0]["rcept_no"]])

    def test_sec_newer_interim_stays_required_while_auxiliary_is_not_required(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            collector = SecEdgarCollector("Synthetic <test@example.invalid>", Path(folder))
            rows = [{"accession_number": f"0000320193-26-00000{index}", "form": form,
                     "primary_document": "report.htm", "filing_date": "2026-10-30", "report_date": period}
                    for index, (form, period) in enumerate([("10-K", "2025-12-31"), ("10-Q", "2026-09-30"), ("10-Q", "2026-06-30")], 1)]
            with patch.object(collector, "_resolve_cik", return_value="0000320193"), patch.object(collector, "_list_filings", return_value=rows), patch.object(collector, "_get", return_value=Mock(content=b"<p>" + BODY + b"</p>")):
                result = collector.collect("Apple Inc.", "AAPL", 3, periodic_only=True)
            self.assertEqual(result["requested_ids"], [row["accession_number"] for row in rows])
            self.assertEqual(result["latest_required_ids"], [row["accession_number"] for row in rows[:2]])


if __name__ == "__main__":
    unittest.main()
