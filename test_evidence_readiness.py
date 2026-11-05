"""Synthetic local text only; no API, model, credentials or corpus access."""
from copy import deepcopy
import hashlib
import unittest

from tools.company_profiles import PROFILES, get_profile
from tools.evidence_readiness import evaluate_readiness, select_official_candidate, validate_readiness_report


DAY = "2026-11-03"


def document(kind: str, ticker: str = "AAPL", *, published: str = "2026-10-29", period: str = "2026-09-30") -> dict:
    profile = next(profile for profile in PROFILES if profile["ticker"] == ticker)
    text = "\n\n".join(f"{kind} financial statement paragraph {i}: Revenue, operating income, geographic demand and cash flow are disclosed for the reporting period. This is synthetic text for an offline test." for i in range(30))
    if profile["market"] == "us":
        issuer = profile["sec_cik"]
        url = f"https://www.sec.gov/Archives/edgar/data/{int(issuer)}/000032019326000001/{kind}.htm"
    else:
        issuer = "00000001"
        url = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=" + published.replace("-", "") + "000001"
    if kind == "earnings":
        url = {"005930.KS": "https://images.samsung.com/is/content/samsung/assets/global/ir/docs/2026_3Q_conference_eng.pdf",
               "000660.KS": "https://news.skhynix.com/en/q3-2026-business-results/",
               "005380.KS": "https://www.hyundai.com/content/dam/hyundai/ww/en/images/company/investor-relations/financial-Information/2026-q3.pdf",
               "035420.KS": "https://www.navercorp.com/api/article/download/offline-fixture",
               "AAPL": "https://www.apple.com/newsroom/2026/10/apple-reports-fourth-quarter-results/",
               "MSFT": "https://www.microsoft.com/en-us/investor/earnings/fy-2027-q1/press-release-webcast"}[ticker]
    return {"company_name": profile["company_name"], "ticker": ticker, "document_type": kind,
            "source_url": url, "published_at": published, "report_date": period,
            "content": text, "content_hash": hashlib.sha256(text.encode()).hexdigest(),
            "identity_verified": True, "provider": "official_ir" if kind == "earnings" else profile["provider"],
            "issuer_id": issuer}


def manifest(ticker: str = "AAPL") -> dict:
    profile = next(profile for profile in PROFILES if profile["ticker"] == ticker)
    return {"company_name": profile["company_name"], "ticker": ticker, "documents": [
        document("annual", ticker, published="2026-03-20", period="2025-12-31"),
        document("interim", ticker), document("earnings", ticker)]}


class EvidenceReadinessTests(unittest.TestCase):
    def test_profiles_require_known_pair_and_preserve_copy(self) -> None:
        self.assertEqual(len(PROFILES), 6)
        self.assertEqual(get_profile("현대차", "005380.KS")["company_name"], "현대자동차")
        self.assertEqual(get_profile("Apple", "aapl")["sec_cik"], "0000320193")
        get_profile("Apple", "AAPL")["aliases"] = ()
        self.assertTrue(get_profile("Apple", "AAPL")["aliases"])
        for company, ticker in (("Apple", "MSFT"), ("현대차증권", "005380.KS"), ("Missing", "MISSING")):
            with self.subTest(company=company), self.assertRaises(ValueError):
                get_profile(company, ticker)

    def test_six_primary_corpora_are_ready_and_reports_omit_original_data(self) -> None:
        for profile in PROFILES:
            with self.subTest(ticker=profile["ticker"]):
                data = manifest(profile["ticker"])
                data["documents"][0]["original_path"] = "PRIVATE LOCAL PATH"
                report = evaluate_readiness(data, DAY)
                self.assertEqual(report["status"], "ready")
                self.assertEqual(report["counts"], {"annual": 1, "interim": 1, "earnings": 1, "report": 0})
                self.assertIs(validate_readiness_report(report, profile["company_name"], profile["ticker"]), report)
                self.assertNotIn("PRIVATE LOCAL PATH", repr(report))
                self.assertNotIn("synthetic text", repr(report))

    def test_empty_corpus_is_valid_but_not_ready(self) -> None:
        data = manifest()
        data["documents"] = []
        report = evaluate_readiness(data, DAY)
        self.assertEqual(report["status"], "insufficient")
        self.assertEqual(report["missing"], ["annual_missing", "recent_financial_missing", "earnings_missing"])
        validate_readiness_report(report, "Apple", "AAPL")

    def test_recent_annual_can_replace_older_interim(self) -> None:
        data = manifest()
        data["documents"] = [document("annual"), document("earnings")]
        self.assertEqual(evaluate_readiness(data, DAY)["status"], "ready")
        data["documents"][0] = document("annual", published="2026-03-20", period="2025-12-31")
        self.assertIn("recent_financial_missing", evaluate_readiness(data, DAY)["missing"])

    def test_metadata_snippets_error_pages_missing_identity_and_bad_hash_do_not_count(self) -> None:
        variants = [{"content": "사업보고서 · 제출인 회사"}, {"body_extraction_status": "snippet_only"}, {"extraction_method": "search_snippet"},
                    {"body_extraction_status": "metadata_only"}, {"content": "Access Denied " * 400},
                    {"identity_verified": False}, {"content_hash": "0" * 64}, {"provider": None}]
        for changes in variants:
            data = manifest()
            data["documents"][2].update(changes)
            with self.subTest(changes=list(changes)):
                self.assertEqual(evaluate_readiness(data, DAY)["missing"], ["earnings_missing"])

    def test_issuer_company_and_official_url_must_match(self) -> None:
        for changes in ({"company_name": "Microsoft Corporation", "ticker": "MSFT"},
                        {"issuer_id": "789019"},
                        {"source_url": "https://www.sec.gov/Archives/edgar/data/789019/000032019326000001/a.htm"},
                        {"source_url": "https://www.sec.gov.evil.example/Archives/edgar/data/320193/000032019326000001/a.htm"},
                        {"source_url": "http://www.sec.gov/Archives/edgar/data/320193/000032019326000001/a.htm"}):
            data = manifest()
            data["documents"][0].update(changes)
            with self.subTest(changes=changes):
                self.assertIn("annual_missing", evaluate_readiness(data, DAY)["missing"])
        data = manifest()
        data["documents"][2]["source_url"] = "https://www.apple.com/shop/earnings"
        self.assertIn("earnings_missing", evaluate_readiness(data, DAY)["missing"])

    def test_official_ir_index_cannot_substitute_for_a_dated_earnings_document(self) -> None:
        for profile in PROFILES:
            data = manifest(profile["ticker"])
            data["documents"][2]["source_url"] = profile["ir_sources"][0]["url"]
            with self.subTest(ticker=profile["ticker"]):
                self.assertIn("earnings_missing", evaluate_readiness(data, DAY)["missing"])

    def test_future_undated_stale_and_out_of_order_reporting_periods_fail_closed(self) -> None:
        for changes in ({"published_at": "2026-11-04"}, {"published_at": "unknown"},
                        {"report_date": "2026-11-01"}, {"report_date": ""},
                        {"published_at": "2025-01-01", "report_date": "2024-12-31"}):
            data = manifest()
            data["documents"][2].update(changes)
            with self.subTest(changes=changes):
                self.assertIn("earnings_missing", evaluate_readiness(data, DAY)["missing"])

    def test_duplicate_body_or_id_cannot_supply_multiple_required_roles(self) -> None:
        data = manifest()
        data["documents"][2].update({key: data["documents"][1][key] for key in ("content", "content_hash")})
        self.assertIn("earnings_missing", evaluate_readiness(data, DAY)["missing"])
        data = manifest()
        for item in data["documents"]:
            item["document_id"] = "same-id"
        report = evaluate_readiness(data, DAY)
        self.assertEqual(sum(report["counts"].values()), 1)
        validate_readiness_report(report, "Apple", "AAPL")

    def test_duplicate_url_and_wrong_dart_receipt_date_do_not_create_coverage(self) -> None:
        data = manifest()
        data["documents"][2]["source_url"] = data["documents"][1]["source_url"]
        data["documents"][2]["provider"] = "sec_edgar"
        self.assertIn("earnings_missing", evaluate_readiness(data, DAY)["missing"])
        data = manifest("005930.KS")
        data["documents"][0]["source_url"] = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261029000001"
        self.assertIn("annual_missing", evaluate_readiness(data, DAY)["missing"])

    def test_local_path_cannot_leak_through_a_document_identifier(self) -> None:
        data = manifest()
        data["documents"][2]["document_id"] = "C:\\Users\\private\\earnings.pdf"
        report = evaluate_readiness(data, DAY)
        self.assertIn("earnings_missing", report["missing"])
        self.assertNotIn("private", repr(report))

    def test_corpus_identity_is_order_and_evaluation_day_independent(self) -> None:
        data = manifest()
        before = evaluate_readiness(data, DAY)
        data["documents"].reverse()
        after = evaluate_readiness(data, "2026-11-04")
        self.assertEqual(before["corpus_hash"], after["corpus_hash"])
        self.assertNotEqual(before["as_of_date"], after["as_of_date"])

    def test_untrusted_report_tampering_is_rejected(self) -> None:
        original = evaluate_readiness(manifest(), DAY)
        variants = [{"counts": {"annual": True, "interim": 1, "earnings": 1, "report": 0}},
                    {"schema_version": True}, {"status": "insufficient"}, {"missing": ["annual_missing"]},
                    {"corpus_hash": "0" * 64}, {"raw_text": "PRIVATE"}, {"as_of_date": None}]
        for changes in variants:
            report = {**deepcopy(original), **changes}
            with self.subTest(changes=list(changes)), self.assertRaises(ValueError):
                validate_readiness_report(report, "Apple", "AAPL")
        report = deepcopy(original)
        report["documents"].append(report["documents"][0])
        with self.assertRaises(ValueError):
            validate_readiness_report(report, "Apple", "AAPL")

    def test_selection_requires_current_ready_reports_then_prefers_new_event(self) -> None:
        apple = evaluate_readiness(manifest(), DAY)
        microsoft = evaluate_readiness(manifest("MSFT"), DAY)
        microsoft["as_of_date"] = "2026-11-02"
        self.assertEqual(select_official_candidate([apple, microsoft], [], DAY)["ticker"], "AAPL")
        microsoft = evaluate_readiness(manifest("MSFT"), DAY)
        history = [{"ticker": "AAPL", "publication_date": "2026-10-30"}]
        selected = select_official_candidate([apple, microsoft], history, DAY)
        self.assertEqual((selected["ticker"], selected["selection_reason"]), ("MSFT", "new_official_event"))
        validate_readiness_report(selected, "Microsoft", "MSFT")

    def test_no_new_event_rotates_oldest_and_does_not_mutate_inputs(self) -> None:
        reports = [evaluate_readiness(manifest(ticker), DAY) for ticker in ("AAPL", "MSFT")]
        history = [{"ticker": "AAPL", "publication_date": "2026-11-01", "documents": None},
                   {"ticker": "MSFT", "publication_date": "2026-10-30"}]
        before = deepcopy(reports)
        selected = select_official_candidate(reports, history, DAY)
        self.assertEqual((selected["ticker"], selected["selection_reason"]), ("MSFT", "rotation"))
        self.assertEqual(reports, before)
        self.assertIsNone(select_official_candidate([], history, DAY))
        invalid = deepcopy(reports[0])
        invalid["status"] = "insufficient"
        self.assertIsNone(select_official_candidate([invalid], history, DAY))


if __name__ == "__main__":
    unittest.main()
