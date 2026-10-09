import unittest
from unittest.mock import patch, Mock

from tools.company_lookup import find_companies, korean_listings


class CompanyLookupTests(unittest.TestCase):
    def test_exact_korean_name_and_spacing(self) -> None:
        rows = ({"name": "삼성전자", "ticker": "005930.KS", "exchange": "KOSPI"},
                {"name": "삼성전자우", "ticker": "005935.KS", "exchange": "KOSPI"})
        with patch("tools.company_lookup.korean_listings", return_value=rows):
            self.assertEqual(find_companies("삼성 전자"), [rows[0]])
            self.assertEqual(len(find_companies("삼성")), 2)

    def test_only_equities_and_unique_symbols(self) -> None:
        equity = {"quoteType": "EQUITY", "symbol": "AAPL", "longname": "Apple Inc.", "exchDisp": "NASDAQ"}
        with patch("tools.company_lookup.yf.Search") as search:
            search.return_value.quotes = [equity, equity, {"quoteType": "FUTURE", "symbol": "SAAPL=F"}]
            self.assertEqual(find_companies("Apple"), [{"name": "Apple Inc.", "ticker": "AAPL", "exchange": "NASDAQ"}])

    def test_search_failure_is_safe(self) -> None:
        with patch("tools.company_lookup.yf.Search", side_effect=TimeoutError()):
            with self.assertRaisesRegex(ValueError, "인터넷"):find_companies("Apple")

    def test_korean_market_suffixes_and_malformed_listing(self) -> None:
        korean_listings.cache_clear()
        response = Mock(content="<table><tr><td>기업</td><td>시장</td><td>000001</td></tr></table>".encode("euc-kr"))
        with patch("tools.company_lookup.requests.get", return_value=response):
            self.assertEqual([r["ticker"] for r in korean_listings()], ["000001.KS", "000001.KQ"])
        korean_listings.cache_clear()
        with patch("tools.company_lookup.requests.get", return_value=Mock(content=b"<table></table>")):
            with self.assertRaises(ValueError):korean_listings()
        korean_listings.cache_clear()


if __name__ == "__main__":unittest.main()
