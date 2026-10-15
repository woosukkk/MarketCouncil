import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pandas as pd

from tools.financial_data import _get_currencies, get_financial_data
from tools.quality_valuation import calculate_quality_metrics, validate_quality_inputs


class FinancialCurrencyTests(unittest.TestCase):
    def company(self, price: object = "USD", financial: object = "EUR") -> SimpleNamespace:
        return SimpleNamespace(fast_info={"currency": price}, get_info=Mock(return_value={"financialCurrency": financial}))

    def facts(self, **changes: object) -> dict:
        return {
            "market_cap": 1000.0,
            "annual_history": [
                {"revenue": 300.0, "free_cash_flow": 30.0, "shares_outstanding": 100.0},
                {"revenue": 200.0, "free_cash_flow": 20.0, "shares_outstanding": 100.0},
                {"revenue": 100.0, "free_cash_flow": 10.0, "shares_outstanding": 100.0},
            ],
            **changes,
        }

    def test_price_and_financial_currencies_are_read_independently(self) -> None:
        company = self.company()
        self.assertEqual(_get_currencies(company), ("USD", "EUR"))
        company.get_info.assert_called_once_with()

    def test_provider_failures_do_not_copy_the_other_currency(self) -> None:
        company = self.company()
        company.get_info.side_effect = RuntimeError("mock provider unavailable")
        self.assertEqual(_get_currencies(company), ("USD", None))
        company = self.company()
        company.fast_info = {}
        self.assertEqual(_get_currencies(company), (None, "EUR"))

    def test_invalid_missing_and_wrong_shape_currency_values_remain_unknown(self) -> None:
        for value in [None, "", "usd", "US", "USDT", 123, ["USD"]]:
            with self.subTest(value=value):
                self.assertEqual(_get_currencies(self.company(value, value)), (None, None))
        company = self.company()
        company.get_info.return_value = None
        self.assertEqual(_get_currencies(company), ("USD", None))

    def test_collection_preserves_distinct_currency_fields_without_live_calls(self) -> None:
        company = self.company("USD", "EUR")
        company.fast_info["market_cap"] = 1000.0
        columns = [pd.Timestamp("2025-12-31"), pd.Timestamp("2024-12-31")]
        company.financials = pd.DataFrame([[300.0, 200.0], [30.0, 20.0]], index=["Total Revenue", "Operating Income"], columns=columns)
        company.cashflow = pd.DataFrame()
        company.balance_sheet = pd.DataFrame()
        with patch.dict(os.environ, {"MARKETCOUNCIL_TICKER": "ADR"}), patch("tools.financial_data.yf.Ticker", return_value=company) as ticker, patch("tools.financial_data.get_latest_price", return_value=(20.0, "2026-10-15")):
            result = get_financial_data("Example ADR")
        ticker.assert_called_once_with("ADR")
        for values in [result, result["financial_facts"]]:
            self.assertEqual(values["price_currency"], "USD")
            self.assertEqual(values["financial_currency"], "EUR")
            self.assertNotIn("currency", values)
        self.assertEqual(result["financial_facts"]["annual_history"][0]["revenue"], 300.0)

    def test_matching_currencies_allow_fcf_yield(self) -> None:
        result = calculate_quality_metrics(self.facts(price_currency="KRW", financial_currency="KRW"))
        self.assertAlmostEqual(result["fcf_yield"], 0.02)
        self.assertNotIn("FCF와 시가총액의 동일 통화 기준", result["missing_inputs"])

    def test_cross_currency_fcf_yield_is_not_calculated(self) -> None:
        facts = self.facts(price_currency="USD", financial_currency="EUR")
        result = calculate_quality_metrics(facts)
        self.assertEqual(result["normalized_fcf"], 20.0)
        self.assertIsNone(result["fcf_yield"])
        self.assertIn("FCF와 시가총액의 동일 통화 기준", result["missing_inputs"])
        self.assertIn("FCF와 시가총액의 동일 통화 기준", validate_quality_inputs(facts))

    def test_new_inputs_with_unknown_or_partial_currencies_fail_closed(self) -> None:
        for currencies in [
            {"price_currency": None, "financial_currency": None},
            {"price_currency": "USD", "financial_currency": None},
            {"price_currency": None, "financial_currency": "USD"},
            {"price_currency": "USD"},
            {"financial_currency": "USD"},
            {"price_currency": "usd", "financial_currency": "usd"},
        ]:
            with self.subTest(currencies=currencies):
                result = calculate_quality_metrics(self.facts(**currencies))
                self.assertIsNone(result["fcf_yield"])
                self.assertIn("FCF와 시가총액의 동일 통화 기준", result["missing_inputs"])

    def test_legacy_inputs_keep_calculation_with_explicit_unverified_assumption(self) -> None:
        for extra in [{}, {"currency": "USD"}]:
            with self.subTest(extra=extra):
                result = calculate_quality_metrics(self.facts(**extra))
                self.assertAlmostEqual(result["fcf_yield"], 0.02)
                self.assertEqual(result["missing_inputs"], [])
                self.assertTrue(any("통화 미검증" in value for value in result["assumptions"]))


if __name__ == "__main__":
    unittest.main()
