"""Offline company-resolution, currency and execution-boundary regressions."""
import os
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pandas as pd

from app.web_analysis_runner import PROJECT_ROOT, run_analysis
from tools.company_lookup import preset_ticker, resolve_ticker
from tools.financial_data import get_financial_data


COMPANIES = (("SK하이닉스", "000660.KS", "KRW"),
             ("현대차", "005380.KS", "KRW"),
             ("NAVER", "035420.KS", "KRW"),
             ("Apple", "AAPL", "USD"),
             ("Microsoft", "MSFT", "USD"))


class MultiCompanyTests(unittest.TestCase):
    def test_presets_and_explicit_aliases_need_no_search(self) -> None:
        with patch("tools.company_lookup.find_companies") as search:
            for company, ticker, _ in COMPANIES:
                with self.subTest(company=company):
                    self.assertEqual(resolve_ticker(company), ticker)
            for alias, ticker in (("SK 하이닉스", "000660.KS"), ("현대자동차", "005380.KS"),
                                  ("naver", "035420.KS"), ("Apple Inc.", "AAPL"),
                                  ("Microsoft Corporation", "MSFT")):
                self.assertEqual(preset_ticker(alias), ticker)
            search.assert_not_called()

    def test_other_names_require_one_candidate_or_one_exact_match(self) -> None:
        rows = [{"name": "Example", "ticker": "EXM"}, {"name": "Example Holdings", "ticker": "EXH"}]
        with patch("tools.company_lookup.find_companies", return_value=rows):
            self.assertEqual(resolve_ticker("Example"), "EXM")
            with self.assertRaisesRegex(ValueError, "후보"):
                resolve_ticker("Exam")
        with patch("tools.company_lookup.find_companies", return_value=rows[:1]):
            self.assertEqual(resolve_ticker("Exam"), "EXM")
        with patch("tools.company_lookup.find_companies", return_value=[]):
            with self.assertRaises(ValueError):
                resolve_ticker("Missing")
        with patch("tools.company_lookup.find_companies", side_effect=ValueError("인터넷")):
            with self.assertRaisesRegex(ValueError, "인터넷"):
                resolve_ticker("Example")

    def test_explicit_listing_is_validated_without_search_or_primary_override(self) -> None:
        with patch("tools.company_lookup.find_companies") as search:
            self.assertEqual(resolve_ticker("Apple Inc.", "APC.DE"), "APC.DE")
            for ticker in ("bad/path", "aapl", "AAPL\n", "../AAPL", "X" * 31):
                with self.subTest(ticker=ticker), self.assertRaises(ValueError):
                    resolve_ticker("Apple", ticker)
            for name in ("", " ", "X" * 121):
                with self.assertRaises(ValueError):
                    resolve_ticker(name, "AAPL")
            search.assert_not_called()

    def test_financials_preserve_each_company_and_provider_currency_in_sequence(self) -> None:
        columns = [pd.Timestamp("2025-12-31"), pd.Timestamp("2024-12-31")]
        with patch.dict(os.environ, {"MARKETCOUNCIL_TICKER": "", "MARKETCOUNCIL_COMPANY": ""}):
            for index, (company_name, ticker, currency) in enumerate(COMPANIES, start=1):
                company = SimpleNamespace(
                    fast_info={"currency": currency, "market_cap": 1000.0 * index},
                    get_info=Mock(return_value={"financialCurrency": currency}),
                    financials=pd.DataFrame([[100.0 * index, 80.0 * index], [10.0, 8.0]],
                                            index=["Total Revenue", "Operating Income"], columns=columns),
                    cashflow=pd.DataFrame(), balance_sheet=pd.DataFrame())
                with self.subTest(company=company_name), patch("tools.financial_data.yf.Ticker", return_value=company) as provider, patch("tools.financial_data.get_latest_price", return_value=(10.0 * index, "2026-11-03")):
                    result = get_financial_data(company_name)
                provider.assert_called_once_with(ticker)
                self.assertEqual(result["ticker"], ticker)
                self.assertEqual(result["price_currency"], currency)
                self.assertEqual(result["financial_currency"], currency)
                self.assertEqual(result["financial_facts"]["annual_history"][0]["revenue"], 100.0 * index)

    def test_stale_known_ticker_or_different_bound_company_stops_before_network(self) -> None:
        for name, owner, ticker in (("Microsoft", "", "AAPL"),
                                     ("NAVER", "삼성전자", "005930.KS"),
                                     ("Other", "Example", "EXM")):
            with self.subTest(company=name), patch.dict(os.environ, {"MARKETCOUNCIL_TICKER": ticker, "MARKETCOUNCIL_COMPANY": owner}), patch("tools.financial_data.yf.Ticker") as provider:
                with self.assertRaises(ValueError):
                    get_financial_data(name)
                provider.assert_not_called()

    def test_bound_desktop_secondary_listing_is_not_replaced_by_preset(self) -> None:
        with patch.dict(os.environ, {"MARKETCOUNCIL_COMPANY": "Apple Inc.", "MARKETCOUNCIL_TICKER": "APC.DE"}), patch("tools.financial_data.yf.Ticker", side_effect=RuntimeError("stop before network")) as provider:
            with self.assertRaisesRegex(RuntimeError, "stop before network"):
                get_financial_data("Apple Inc.")
            provider.assert_called_once_with("APC.DE")

    def test_local_runner_overrides_parent_ticker_and_company_for_every_preset(self) -> None:
        path = PROJECT_ROOT / "results" / "analysis_debate" / "test" / "analysis_debate_test.json"
        with patch.dict(os.environ, {"MARKETCOUNCIL_TICKER": "005930.KS", "MARKETCOUNCIL_COMPANY": "삼성전자"}), patch("app.web_analysis_runner.subprocess.run") as run, patch.object(Path, "is_file", return_value=True):
            run.return_value = subprocess.CompletedProcess([], 0, f"토론 원본 JSON: {path}\n", "")
            for company, ticker, _ in COMPANIES:
                with self.subTest(company=company):
                    self.assertEqual(run_analysis(company), path.relative_to(PROJECT_ROOT))
                    self.assertEqual(run.call_args.kwargs["input"], company + "\n")
                    self.assertEqual(run.call_args.kwargs["env"]["MARKETCOUNCIL_TICKER"], ticker)
                    self.assertEqual(run.call_args.kwargs["env"]["MARKETCOUNCIL_COMPANY"], company)
            self.assertEqual(os.environ["MARKETCOUNCIL_TICKER"], "005930.KS")


if __name__ == "__main__":
    unittest.main()
