import copy
import unittest

from tools.citation_quality import assess_issue_evidence


class CitationQualityTests(unittest.TestCase):
    def assess(self, claim: str, quote: str, published: object = "2026-10-01", as_of: object = "2026-10-15") -> dict:
        catalog = [{"source_id": "S1", "published_at": published, "content": quote,
                    "quotes": [{"quote_id": "Q1", "text": quote}]}]
        issue = {"claim": claim, "evidence": [{"source_id": "S1", "quote_id": "Q1", "exact_quote": quote}]}
        return assess_issue_evidence(issue, catalog, as_of)

    def test_currency_percent_and_shares_are_unit_normalized(self) -> None:
        result = self.assess("매출 1조원, 영업이익률 12%, 발행 주식수 100만주", "매출 10,000억원, 이익률 12퍼센트, 발행 1,000,000주")
        self.assertEqual(result["claim_number_count"], 3)
        self.assertEqual(result["unmatched_number_count"], 0)
        self.assertEqual(result["numeric_status"], "values_present")
        self.assertEqual(result["semantic_status"], "not_evaluated")

    def test_display_precision_allows_rounding_but_not_a_different_value(self) -> None:
        result = self.assess("이익률 0.79%, 매출 11.265조원", "이익률 0.793548%, 매출 11.26521375조원")
        self.assertEqual(result["unmatched_number_count"], 0)
        self.assertEqual(result["numeric_status"], "values_present")
        self.assertEqual(result["semantic_status"], "not_evaluated")
        for quoted in ["0.80%", "0.795%"]:
            with self.subTest(quoted=quoted):
                self.assertIn("number_not_in_quotes", self.assess("이익률 0.79%", quoted)["warnings"])
        self.assertEqual(self.assess("매출 $1 billion", "매출 USD 1,000 million")["unmatched_number_count"], 0)

    def test_scientific_notation_is_one_value_with_its_original_unit(self) -> None:
        quote = "FCF yield=1e-05% (원래 비율 1e-07)"
        correct = self.assess("FCF yield 0.00001%", quote)
        self.assertEqual(correct["numeric_status"], "values_present")
        self.assertEqual(correct["unmatched_number_count"], 0)
        self.assertIn("number_not_in_quotes", self.assess("FCF yield -5%", quote)["warnings"])
        money = self.assess("시가총액 100000000000000000000원", "시가총액=1e+20 KRW")
        self.assertEqual(money["numeric_status"], "values_present")
        self.assertIn("number_not_in_quotes", self.assess("시가총액 20원", "시가총액=1e+20 KRW")["warnings"])

    def test_unsupported_value_is_warning_even_when_identity_matches(self) -> None:
        result = self.assess("이익률 15%", "이익률 12%")
        self.assertEqual(result["identity_status"], "matched")
        self.assertEqual(result["warnings"], ["number_not_in_quotes"])
        self.assertEqual(result["unmatched_number_count"], 1)

    def test_currency_dimensions_and_signed_percent_are_not_conflated(self) -> None:
        for claim, quote in [("매출 100원", "매출 100달러"), ("수익률 -10%", "수익률 10%"), ("증가폭 10%p", "수익률 10%")]:
            with self.subTest(claim=claim):
                self.assertIn("number_not_in_quotes", self.assess(claim, quote)["warnings"])

    def test_calendar_values_and_week_horizons_are_not_financial_numbers(self) -> None:
        for claim in ["2026년 1분기, 향후 1~4주 전망", "향후 1주 동안 주식을 보유한다", "앞으로 4주 내 주식 매수 검토", "향후 1-4주 주식을 보유한다"]:
            with self.subTest(claim=claim):
                result = self.assess(claim, "확인 가능한 자료")
                self.assertEqual(result["claim_number_count"], 0)
                self.assertEqual(result["numeric_status"], "not_applicable")
        self.assertEqual(self.assess("주식 1주 매수", "주식 1주 매수")["claim_number_count"], 1)

    def test_numbers_present_do_not_assert_direction_or_truth(self) -> None:
        result = self.assess("매출이 30% 감소했다", "매출이 30% 증가했다")
        self.assertEqual(result["numeric_status"], "values_present")
        self.assertEqual(result["semantic_status"], "not_evaluated")
        self.assertNotIn("contradiction", result)

    def test_missing_and_future_dates_are_separate_from_identity(self) -> None:
        for date, warning in [("", "source_date_missing"), ("not a date", "source_date_missing"), ("2026-10-16", "future_source")]:
            with self.subTest(date=date):
                result = self.assess("매출 1조원", "매출 1조원", published=date)
                self.assertEqual(result["identity_status"], "matched")
                self.assertIn(warning, result["warnings"])
        self.assertNotIn("future_source", self.assess("매출 1조원", "매출 1조원", published="20261015")["warnings"])

    def test_only_old_forecasts_for_short_term_claims_warn(self) -> None:
        result = self.assess("향후 1~4주 매출 전망", "올해 매출은 증가할 것으로 전망한다", published="2026-01-01")
        self.assertIn("stale_forecast", result["warnings"])
        self.assertNotIn("stale_forecast", self.assess("향후 1~4주 매출 검토", "지난해 매출은 1조원이었다", published="2026-01-01")["warnings"])
        self.assertNotIn("stale_forecast", self.assess("장기 매출 검토", "매출 증가를 전망한다", published="2026-01-01")["warnings"])
        self.assertNotIn("stale_forecast", self.assess("향후 1~4주 전망", "매출 증가를 전망한다", published="2026-07-17")["warnings"])

    def test_invalid_as_of_date_does_not_guess_current_date(self) -> None:
        result = self.assess("향후 1~4주 전망", "매출 증가를 전망한다", published="2099-01-01", as_of=None)
        self.assertFalse(result["as_of_date_valid"])
        self.assertNotIn("future_source", result["warnings"])
        self.assertNotIn("stale_forecast", result["warnings"])

    def test_unknown_ids_and_altered_quote_are_invalid(self) -> None:
        catalog = [{"source_id": "S1", "content": "매출 12% 증가", "quotes": [{"quote_id": "Q1", "text": "매출 12% 증가"}]}]
        for item in [{"source_id": "missing", "quote_id": "Q1"}, {"source_id": "S1", "quote_id": "missing"}, {"source_id": "S1", "quote_id": "Q1", "exact_quote": "매출 15% 증가"}]:
            with self.subTest(item=item):
                result = assess_issue_evidence({"claim": "매출 15% 증가", "evidence": [item]}, catalog, "2026-10-15")
                self.assertEqual(result["identity_status"], "invalid")
                self.assertEqual(result["semantic_status"], "not_evaluated")
                self.assertIn("number_not_in_quotes", result["warnings"])

    def test_numbers_in_supporting_fields_are_checked(self) -> None:
        catalog = [{"source_id": "S1", "published_at": "2026-10-01",
                    "quotes": [{"quote_id": "Q1", "text": "이익률 12%"}]}]
        for field in ("response", "warrant", "example_or_data"):
            with self.subTest(field=field):
                issue = {"claim": "수익성을 검토했다", field: "이익률 15%",
                         "evidence": [{"source_id": "S1", "quote_id": "Q1"}]}
                result = assess_issue_evidence(issue, catalog, "2026-10-15")
                self.assertEqual(result["claim_number_count"], 1)
                self.assertEqual(result["numeric_status"], "needs_review")
                self.assertIn("number_not_in_quotes", result["warnings"])

    def test_opponent_and_conditional_fields_are_not_own_assertions(self) -> None:
        issue = {"claim": "이익률 12%", "target_claim": "이익률 99%",
                 "qualifier": "이익률 50%라면 향후 1주 전망", "concession": "이익률 90% 가정",
                 "evidence": [{"source_id": "S1", "quote_id": "Q1"}]}
        catalog = [{"source_id": "S1", "published_at": "2026-01-01",
                    "quotes": [{"quote_id": "Q1", "text": "이익률 12% 전망"}]}]
        result = assess_issue_evidence(issue, catalog, "2026-10-15")
        self.assertEqual(result["claim_number_count"], 1)
        self.assertEqual(result["numeric_status"], "values_present")
        self.assertEqual(result["warnings"], [])

    def test_short_term_horizon_in_supporting_fields_uses_the_same_scope(self) -> None:
        catalog = [{"source_id": "S1", "published_at": "2026-01-01",
                    "quotes": [{"quote_id": "Q1", "text": "매출 증가를 전망한다"}]}]
        for field in ("response", "warrant", "example_or_data"):
            with self.subTest(field=field):
                issue = {"claim": "매출을 검토한다", field: "향후 1~4주 전망",
                         "evidence": [{"source_id": "S1", "quote_id": "Q1"}]}
                result = assess_issue_evidence(issue, catalog, "2026-10-15")
                self.assertEqual(result["claim_number_count"], 0)
                self.assertIn("stale_forecast", result["warnings"])

    def test_no_evidence_has_no_identity_and_does_not_mutate_inputs(self) -> None:
        issue = {"claim": "매출 15% 증가", "evidence": []}
        catalog = []
        original = copy.deepcopy((issue, catalog))
        result = assess_issue_evidence(issue, catalog, "2026-10-15")
        self.assertEqual(result["identity_status"], "missing")
        self.assertEqual((issue, catalog), original)
        self.assertNotIn("claim", result)
        self.assertNotIn("exact_quote", result)

    def test_valid_inputs_remain_unchanged_and_prompt_catalog_can_omit_content(self) -> None:
        issue = {"claim": "매출 1조원", "evidence": [{"source_id": "S1", "quote_id": "Q1"}]}
        catalog = [{"source_id": "S1", "published_at": "2026-10-01", "quotes": [{"quote_id": "Q1", "text": "매출 1조원"}]}]
        original = copy.deepcopy((issue, catalog))
        result = assess_issue_evidence(issue, catalog, "2026-10-15")
        self.assertEqual(result["identity_status"], "matched")
        self.assertEqual(result["warnings"], [])
        self.assertEqual((issue, catalog), original)


if __name__ == "__main__":
    unittest.main()
