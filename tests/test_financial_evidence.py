import unittest
from tools.evidence_catalog import EvidenceCatalog
from tools.citation_quality import assess_issue_evidence


class FinancialEvidenceTests(unittest.TestCase):
    def data(self) -> dict:
        history = [{"period": f"{year}-12-31", "revenue": 200, "free_cash_flow": fcf,
                    "shares_outstanding": shares, "notes": "annual input " * 45}
                   for year, fcf, shares in [(2025, 12e12, 111), (2024, 10e12, 105), (2023, 11e12, 100)]]
        return {"ticker": "005930.KS", "price_date": "20261015", "current_revenue": "200", "previous_revenue": "180",
                "financial_facts": {"current_price": 100, "market_cap": 1.4e15, "price_currency": "KRW",
                                    "financial_currency": "KRW", "annual_history": history},
                "derived_metrics": {"normalized_fcf": 11265213750000, "fcf_yield": .007935489212,
                                    "dilution_rate": .11, "debt_to_equity": .059, "missing_inputs": [], "assumptions": []}}

    def test_derived_values_are_available_despite_large_annual_inputs(self) -> None:
        entry = EvidenceCatalog.build(self.data(), [], [])[0]
        prompt = EvidenceCatalog.for_prompt([entry])[0]
        self.assertLessEqual(len(prompt["quotes"]), 16)
        cases = [("normalized_fcf", "정규화 FCF 11.265조원", ["11265213750000", "2025-12-31", "평균", "KRW"]),
                 ("fcf_yield", "FCF 수익률 0.79%", ["0.7935489212%", "2026-10-15", "시가총액", "2023-12-31"]),
                 ("dilution_rate", "발행 주식 수 변화율 11%", ["111", "100", "2023-12-31", "EPS 희석률 아님"])]
        for metric, claim, expected in cases:
            with self.subTest(metric=metric):
                quote = next(q for q in prompt["quotes"] if f"({metric})=" in q["text"])
                for value in expected:
                    self.assertIn(value, quote["text"])
                item = {"source_id": entry["source_id"], "quote_id": quote["quote_id"]}
                quality = assess_issue_evidence({"claim": claim, "evidence": [item]}, [entry], "2026-10-15")
                self.assertEqual(quality["numeric_status"], "values_present")
                self.assertEqual(quality["semantic_status"], "not_evaluated")
                resolved = EvidenceCatalog.resolve_quote(item, [entry], "E-1")
                self.assertTrue(resolved["verified"])
                self.assertEqual(resolved["exact_quote"], quote["text"])
                self.assertIn(quote["text"], entry["content"])

    def test_individual_annual_inputs_have_explicit_units(self) -> None:
        entry = EvidenceCatalog.build(self.data(), [], [])[0]
        for metric, claim in [("normalized_fcf", "2025년 FCF 12조원"), ("dilution_rate", "2024년 발행 주식 105주")]:
            with self.subTest(metric=metric):
                quote = next(q for q in entry["quotes"] if f"({metric})=" in q["text"])
                result = assess_issue_evidence({"claim": claim, "evidence": [{"source_id": "FIN-001", "quote_id": quote["quote_id"]}]}, [entry], "2026-10-15")
                self.assertEqual(result["numeric_status"], "values_present")

    def test_units_and_current_previous_periods_stay_separate(self) -> None:
        data = self.data()
        data["financial_facts"]["price_currency"] = "USD"
        entry = EvidenceCatalog.build(data, [], [])[0]
        self.assertIn("100 USD", entry["quotes"][0]["text"])
        revenue = entry["quotes"][1]["text"]
        self.assertIn("현재 연간(2025-12-31)=200 KRW", revenue)
        self.assertIn("이전 연간(2024-12-31)=180 KRW", revenue)
        debt = next(q["text"] for q in entry["quotes"] if "(debt_to_equity)=" in q["text"])
        self.assertIn("2025-12-31", debt)
        self.assertNotIn("2024-12-31", debt)

    def test_missing_units_periods_dates_are_never_guessed_from_ticker(self) -> None:
        entry = EvidenceCatalog.build({"ticker": "005930.KS", "current_revenue": 100, "derived_metrics": {"normalized_fcf": 50}}, [], [])[0]
        self.assertEqual(entry["published_at"], "")
        self.assertIn("재무 통화 단위 미제공", entry["content"])
        self.assertIn("기간 미제공", entry["content"])
        self.assertNotIn("KRW", entry["content"])
        self.assertNotIn("2026", entry["content"])

    def test_generic_catalog_dates_are_normalized_before_prompting(self) -> None:
        documents = [{"published_date": day, "content": "A sufficiently long published evidence passage.", "url": "https://example.com/report"}
                     for day in ["20260821", "2026-10-14T15:30:00Z", "2026-10-15invalid"]]
        catalog = EvidenceCatalog.from_web_documents(documents)
        self.assertEqual([item["published_at"] for item in catalog], ["2026-08-21", "2026-10-15", ""])


if __name__ == "__main__":
    unittest.main()
