"""Synthetic official IR pages; no external HTTP, authentication or model calls."""
import hashlib
import io
import json
import socket
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from tools.company_profiles import PROFILES, get_profile
from tools.company_evidence_collector import CompanyEvidenceCollector
from tools.evidence_readiness import evaluate_readiness
from tools.official_ir_collector import OfficialIRCollector, _period


def page(company: str = "Apple Inc.", metadata: str = '<meta property="article:published_time" content="2026-10-29T12:00:00Z">',
         heading: str = "Quarterly financial results", extra: str = "") -> bytes:
    text = (company + " reported revenue of $12.3 billion and operating income of $4.5 billion for the quarter ended September 30, 2026. ") * 15
    return ('<!doctype html><html><head><title>' + company + " " + heading + '</title>' + metadata +
            '</head><body><nav>remove navigation</nav><script>remove script</script><h1>' + heading + '</h1>' + extra + '<p>' + text + '</p></body></html>').encode()


def response(body: bytes, status: int = 200, headers: dict | None = None) -> Mock:
    return Mock(status_code=status, headers=headers or {"Content-Type": "text/html"},
                iter_content=Mock(return_value=[body]), close=Mock())


def pdf(lines: list[str]) -> bytes:
    escaped = [line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for line in lines]
    content = ("BT /F1 9 Tf 12 TL 30 750 Td " + " T* ".join("(" + line + ") Tj" for line in escaped) + " ET").encode()
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
               b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    output, offsets = io.BytesIO(), [0]
    output.write(b"%PDF-1.4\n")
    for index, obj in enumerate(objects, 1):
        offsets.append(output.tell())
        output.write(str(index).encode() + b" 0 obj\n" + obj + b"\nendobj\n")
    xref = output.tell()
    output.write(b"xref\n0 6\n0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.write(f"{offset:010d} 00000 n \n".encode())
    output.write(b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n" + str(xref).encode() + b"\n%%EOF\n")
    return output.getvalue()


class OfficialIRCollectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="official-ir-한글-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.collector = OfficialIRCollector(self.base)
        self.collector.session.get = Mock(return_value=response(page()))
        resolver = patch("tools.official_ir_collector.socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))])
        resolver.start()
        self.addCleanup(resolver.stop)
        self.url = "https://www.apple.com/newsroom/2026/10/synthetic-quarterly-results/"

    def collect(self, **kwargs: object) -> dict:
        return self.collector.collect("Apple", "AAPL", source_urls=[self.url], **kwargs)

    def test_dated_report_preserves_actual_body_and_file_hashes(self) -> None:
        result = self.collect()
        self.assertEqual(result["failures"], [])
        self.assertEqual(len(result["documents"]), 1)
        document = result["documents"][0]
        self.assertEqual((document["company_name"], document["ticker"], document["issuer_id"]), ("Apple Inc.", "AAPL", "0000320193"))
        self.assertEqual((document["published_at"], document["report_date"]), ("2026-10-29", "2026-09-30"))
        self.assertEqual((document["provider"], document["document_type"]), ("official_ir", "earnings"))
        self.assertRegex(document["document_id"], r"^IR-[a-f0-9]{24}$")
        self.assertTrue(document["identity_verified"])
        self.assertNotIn("remove script", document["content"])
        self.assertNotIn("remove navigation", document["content"])
        self.assertTrue(Path(document["original_path"]).is_relative_to(self.base / "AAPL/ir"))
        self.assertEqual(document["original_hash"], hashlib.sha256(Path(document["original_path"]).read_bytes()).hexdigest())
        self.assertEqual(document["content_hash"], hashlib.sha256(Path(document["text_path"]).read_text(encoding="utf-8").encode()).hexdigest())
        self.assertEqual(self.collector.session.get.call_args.kwargs["allow_redirects"], False)

    def test_jsonld_time_and_visible_dateline_dates_are_supported(self) -> None:
        variants = [
            ('<script type="application/ld+json">' + json.dumps({"@type": "NewsArticle", "datePublished": "2026-10-29"}) + '</script>', ""),
            ('', '<time datetime="2026-10-29">October 29, 2026</time>'),
            ('', '<p>CUPERTINO, California — October 29, 2026 —</p>'),
        ]
        for metadata, extra in variants:
            with self.subTest(metadata=metadata):
                self.collector.session.get.return_value = response(page(metadata=metadata, extra=extra))
                self.assertEqual(self.collect()["documents"][0]["published_at"], "2026-10-29")

    def test_missing_publication_is_not_replaced_with_the_period_date(self) -> None:
        self.collector.session.get.return_value = response(page(metadata=""))
        result = self.collect()
        self.assertEqual(result["documents"], [])
        self.assertEqual(result["failures"][0]["code"], "publication_date_missing_or_future")

    def test_future_announcement_and_missing_financial_values_are_rejected(self) -> None:
        for raw in [page(heading="Will announce quarterly earnings release date"),
                    page().replace(b"revenue", b"opportunities").replace(b"operating income", b"product launches"),
                    page().replace(b"2026-10-29T12:00:00Z", (datetime.now(timezone.utc).date() + timedelta(days=3)).isoformat().encode())]:
            with self.subTest(raw=raw[:100]):
                self.collector.session.get.return_value = response(raw)
                self.assertEqual(self.collect()["documents"], [])

    def test_us_fiscal_quarter_label_does_not_guess_calendar_period(self) -> None:
        raw = page().replace(b"quarter ended September 30, 2026", b"fiscal 2027 Q1")
        self.collector.session.get.return_value = response(raw)
        self.assertEqual(self.collect()["failures"][0]["code"], "report_period_missing")
        self.assertEqual(_period("SK hynix Announces 3Q26 Financial Results", get_profile("SK하이닉스", "000660.KS")).isoformat(), "2026-09-30")

    def test_microsoft_release_heading_can_be_nested_under_press_release_header(self) -> None:
        url = "https://www.microsoft.com/en-us/Investor/earnings/synthetic-quarter-results"
        self.collector.session.get.return_value = response(page(company="Microsoft Corporation", heading="Press Release & Webcast", extra="<h2>Earnings Release FY27 Q1</h2>"))
        result = self.collector.collect("Microsoft", "MSFT", source_urls=[url])
        self.assertEqual(result["failures"], [])
        self.assertEqual(result["documents"][0]["report_date"], "2026-09-30")

    def test_actual_synthetic_pdf_parser_uses_visible_publication_and_period(self) -> None:
        lines = ["Apple Inc. Quarterly earnings results", "October 29, 2026"]
        lines += ["Apple Inc. revenue was $12 billion and operating income was $4 billion; quarter ended September 30, 2026."] * 15
        self.collector.session.get.return_value = response(pdf(lines), headers={"Content-Type": "application/pdf"})
        result = self.collect()
        self.assertEqual(result["failures"], [])
        self.assertEqual(result["documents"][0]["report_date"], "2026-09-30")
        self.assertTrue(result["documents"][0]["original_path"].endswith(".pdf"))

    def test_index_page_is_discovery_only_and_does_not_become_a_document(self) -> None:
        source = get_profile("Microsoft", "MSFT")["ir_sources"][0]["url"]
        target = "https://www.microsoft.com/en-us/Investor/earnings/synthetic-quarter-results"
        index = ('<html><h1>Microsoft Investor Relations</h1><a href="' + target + '">2026 quarterly earnings results</a></html>').encode()
        self.collector.session.get.side_effect = [response(index), response(page(company="Microsoft Corporation"))]
        result = self.collector.collect("Microsoft", "MSFT")
        self.assertEqual(result["failures"], [])
        self.assertEqual([doc["source_url"] for doc in result["documents"]], [target])
        self.assertNotEqual(result["documents"][0]["source_url"], source)

    def test_later_news_index_is_not_starved_by_an_earlier_pdf_archive(self) -> None:
        profile = get_profile("삼성전자", "005930.KS")
        seeds = [source["url"] for source in profile["ir_sources"]]
        article = "https://news.samsung.com/global/synthetic-quarterly-results"
        archive_links = "".join(f'<a href="https://images.samsung.com/is/content/samsung/assets/global/ir/docs/synthetic-{index}.pdf">PDF</a>' for index in range(20))
        archive_page = ("<html><h1>Earnings archive</h1>" + archive_links + "</html>").encode()
        news_page = ('<html><h1>Press Releases</h1><a href="' + article + '">Samsung quarterly financial results</a></html>').encode()
        def fetch(url: str, **kwargs: object) -> Mock:
            if url == seeds[0]:
                return response(archive_page)
            if urlsplit_host(url) == "images.samsung.com":
                return response(b"", 404)
            if url == seeds[2]:
                return response(news_page)
            if url == article:
                return response(page(company="Samsung Electronics"))
            raise AssertionError("Unexpected source")
        def urlsplit_host(value: str) -> str:
            from urllib.parse import urlsplit
            return urlsplit(value).hostname
        self.collector.session.get.side_effect = fetch
        result = self.collector.collect("삼성전자", "005930.KS", issuer_id="00126380", limit=1)
        self.assertEqual([doc["source_url"] for doc in result["documents"]], [article])
        self.assertLess(self.collector.session.get.call_count, 12)
        self.assertFalse(any(call.args[0].endswith(".pdf") for call in self.collector.session.get.call_args_list))

    def test_official_pdf_download_without_filename_extension_is_discovered(self) -> None:
        target = "https://www.navercorp.com/api/article/download/synthetic-quarter"
        index = b'<html><h1>Earnings</h1><table><tr><td>2Q 2026 NAVER Earnings Release</td><td><a href="/api/article/download/synthetic-quarter">File PDF Download</a></td></tr></table></html>'
        lines = ["NAVER Quarterly earnings results", "August 7, 2026"]
        lines += ["NAVER revenue was $12 billion and operating income was $4 billion; quarter ended June 30, 2026."] * 15
        document = pdf(lines)
        self.collector.session.get.side_effect = lambda url, **kwargs: response(document) if "/api/article/download/" in url else response(index)
        result = self.collector.collect("NAVER", "035420.KS", limit=1)
        self.assertEqual(result["failures"], [])
        self.assertEqual(result["documents"][0]["source_url"], target)
        self.assertEqual(result["documents"][0]["published_at"], "2026-08-07")

    def test_newer_quarter_failure_is_not_hidden_by_an_older_success(self) -> None:
        latest = "https://news.skhynix.com/en/q3-2026-business-results/"
        previous = "https://news.skhynix.com/en/q2-2026-business-results/"
        old = page(company="SK hynix", metadata='<meta property="article:published_time" content="2026-07-29">').replace(b"September 30, 2026", b"June 30, 2026")
        self.collector.session.get.side_effect = [response(b"", 404), response(old)]
        result = self.collector.collect("SK하이닉스", "000660.KS", source_urls=[latest, previous], limit=1)
        self.assertEqual(len(result["documents"]), 1)
        self.assertEqual(result["documents"][0]["report_date"], "2026-06-30")
        self.assertTrue(result["latest_earnings_failed"])

    def test_same_period_html_can_replace_a_failed_pdf(self) -> None:
        failed = "https://images.samsung.com/is/content/samsung/assets/global/ir/docs/2026_3Q_synthetic.pdf"
        alternative = "https://news.samsung.com/global/synthetic-third-quarter-2026-results"
        self.collector.session.get.side_effect = [response(b"", 404), response(page(company="Samsung Electronics"))]
        result = self.collector.collect("삼성전자", "005930.KS", source_urls=[failed, alternative], limit=1)
        self.assertEqual(result["documents"][0]["report_date"], "2026-09-30")
        self.assertFalse(result["latest_earnings_failed"])

    def test_unknown_archive_pdf_failure_does_not_override_a_dated_release(self) -> None:
        current = "https://www.microsoft.com/en-us/Investor/earnings/synthetic-quarter-results"
        other = "https://www.microsoft.com/en-us/Investor/earnings/archive.pdf"
        index = (f'<html><a href="{current}">Quarterly financial results</a><a href="{other}">PDF</a></html>').encode()
        self.collector.session.get.side_effect = [response(index), response(page(company="Microsoft Corporation")), response(b"", 404)]
        result = self.collector.collect("Microsoft", "MSFT", limit=2)
        self.assertEqual(len(result["documents"]), 1)
        self.assertFalse(result["latest_earnings_failed"])

    def test_new_fiscal_quarter_failure_is_not_replaced_by_previous_year_q4(self) -> None:
        latest = "https://www.microsoft.com/en-us/Investor/earnings/FY-2027-Q1/press-release-webcast"
        previous = "https://www.microsoft.com/en-us/Investor/earnings/FY-2026-Q4/press-release-webcast"
        old = page(company="Microsoft Corporation", metadata='<meta property="article:published_time" content="2026-07-29">', extra="<h2>Earnings Release FY26 Q4</h2>").replace(b"September 30, 2026", b"June 30, 2026")
        self.collector.session.get.side_effect = [response(b"", 503), response(old)]
        result = self.collector.collect("Microsoft", "MSFT", source_urls=[latest, previous], limit=1)
        self.assertEqual(len(result["documents"]), 1)
        self.assertTrue(result["latest_earnings_failed"])

    def test_unverified_known_newer_candidate_after_limit_also_blocks(self) -> None:
        previous = "https://news.skhynix.com/en/q2-2026-business-results/"
        latest = "https://news.skhynix.com/en/q3-2026-business-results/"
        old = page(company="SK hynix", metadata='<meta property="article:published_time" content="2026-07-29">').replace(b"September 30, 2026", b"June 30, 2026")
        self.collector.session.get.return_value = response(old)
        result = self.collector.collect("SK하이닉스", "000660.KS", source_urls=[previous, latest], limit=1)
        self.assertEqual(self.collector.session.get.call_count, 1)
        self.assertTrue(result["latest_earnings_failed"])

    def test_unvisited_explicit_required_source_without_date_hint_also_blocks(self) -> None:
        other = "https://www.apple.com/newsroom/required-second-release"
        self.collector.session.get.return_value = response(page())
        result = self.collector.collect("Apple", "AAPL", source_urls=[self.url, other], limit=1)
        self.assertEqual(len(result["documents"]), 1)
        self.assertEqual(self.collector.session.get.call_count, 1)
        self.assertTrue(result["latest_earnings_failed"])

    def test_redirect_is_checked_again_before_a_second_request(self) -> None:
        self.collector.session.get.return_value = response(b"", 302, {"Location": "https://evil.example/newsroom/results"})
        result = self.collect()
        self.assertEqual(result["documents"], [])
        self.assertEqual(result["failures"][0]["code"], "unverified_source_url")
        self.assertEqual(self.collector.session.get.call_count, 1)

    def test_public_url_paths_identity_and_private_addresses_are_guarded(self) -> None:
        for url in ["http://www.apple.com/newsroom/result", "https://www.apple.com.evil.example/newsroom/result",
                    "https://www.apple.com/newsroom/%2e%2e/private", "https://user:password@www.apple.com/newsroom/result",
                    "https://www.apple.com/private/results"]:
            with self.subTest(url=url):
                self.collector.session.get.reset_mock()
                result = self.collector.collect("Apple", "AAPL", source_urls=[url])
                self.assertEqual(result["documents"], [])
                self.collector.session.get.assert_not_called()
        with self.assertRaisesRegex(ValueError, "issuer_identity_mismatch"):
            self.collect(issuer_id="0000789019")
        with patch("tools.official_ir_collector.socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]):
            self.assertEqual(self.collect()["failures"][0]["code"], "non_public_source_address")

    def test_size_limit_and_truncated_pdf_fail_without_accepting_evidence(self) -> None:
        for value in [response(page(), headers={"Content-Length": "999999999"}), response(b"%PDF-not-a-valid-pdf")]:
            with self.subTest(headers=value.headers):
                self.collector.session.get.return_value = value
                result = self.collect()
                self.assertEqual(result["documents"], [])
                self.assertTrue(result["failures"])
        with patch("tools.official_ir_collector.MAX_BYTES", 100):
            self.collector.session.get.return_value = response(page())
            self.assertEqual(self.collect()["failures"][0]["code"], "source_size_limit_exceeded")

    def test_six_explicit_company_sources_produce_gate_acceptable_earnings(self) -> None:
        urls = ["https://news.samsung.com/global/synthetic-quarter-results",
                "https://news.skhynix.com/en/synthetic-quarter-results/",
                "https://www.hyundai.com/worldwide/en/company/ir/synthetic-earnings.html",
                "https://www.navercorp.com/en/investment/synthetic-earnings.html",
                self.url,
                "https://www.microsoft.com/en-us/Investor/earnings/synthetic-quarter-results"]
        for profile, url in zip(PROFILES, urls):
            with self.subTest(ticker=profile["ticker"]):
                self.collector.session.get.return_value = response(page(company=profile["company_name"]))
                result = self.collector.collect(profile["company_name"], profile["ticker"], issuer_id=profile["sec_cik"] or "00000001", source_urls=[url])
                self.assertEqual(result["failures"], [])
                document = result["documents"][0]
                self.assertEqual((document["company_name"], document["ticker"]), (profile["company_name"], profile["ticker"]))
                cache = CompanyEvidenceCollector(self.base)
                cache.save({"company_name": profile["company_name"], "ticker": profile["ticker"], "issuer_id": document["issuer_id"], "documents": [document], "failures": []})
                hydrated = cache.load(profile["company_name"], profile["ticker"])
                self.assertEqual(hydrated["failures"], [])
                report = evaluate_readiness(hydrated, "2026-11-03")
                self.assertEqual(report["counts"]["earnings"], 1)
                self.assertNotIn("earnings_missing", report["missing"])
                self.assertEqual(report["status"], "insufficient", "An earnings release alone is not an annual/interim corpus")


if __name__ == "__main__":
    unittest.main()
