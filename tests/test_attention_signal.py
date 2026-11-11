"""Synthetic numbers only; no network, market data or news service."""
import unittest
from datetime import date, datetime, timedelta, timezone
from email.utils import format_datetime
from types import SimpleNamespace

from tools.attention_signal import NEWS_URL, attention_scores, combine, naver_news, news_surge, price_move

DAY = date(2026, 11, 3)
NOW = datetime(2026, 11, 3, 0, 30, tzinfo=timezone.utc)


def closes(last_move: float, days: int = 40) -> list[tuple[date, float]]:
    values, price = [], 100.0
    for index in range(days):
        price *= 1.01 if index % 2 else 0.99
        values.append((DAY - timedelta(days=days - index), price))
    values.append((DAY, price * (1 + last_move)))
    return values


def moments(recent: int, previous: int, older: int = 1) -> list[datetime]:
    rows = [NOW - timedelta(hours=1 + index % 20) for index in range(recent)]
    rows += [NOW - timedelta(hours=25 + index % 20) for index in range(previous)]
    return rows + [NOW - timedelta(hours=60)] * older


def pages(rows: list[datetime], calls: list, status: int = 200):
    def get(url: str, *, params: dict, headers: dict, timeout: int) -> SimpleNamespace:
        calls.append((url, params, headers))
        chunk = rows[params["start"] - 1:params["start"] + 99]
        items = [{"pubDate": format_datetime(moment)} for moment in chunk]
        return SimpleNamespace(status_code=status, json=lambda: {"items": items})
    return get


class AttentionSignalTests(unittest.TestCase):
    def test_price_move_is_relative_to_own_volatility_and_ignores_later_dates(self) -> None:
        calm, sharp = price_move(closes(0.01), DAY), price_move(closes(0.05), DAY)
        self.assertAlmostEqual(calm, 1.0, delta=0.15)
        self.assertGreater(sharp, 4)
        self.assertAlmostEqual(price_move(closes(-0.05), DAY), sharp, delta=0.5)
        self.assertEqual(price_move(closes(0.05) + [(DAY + timedelta(days=1), 500.0)], DAY), sharp)
        self.assertIsNone(price_move(closes(0.05, days=10), DAY))
        self.assertIsNone(price_move([(DAY - timedelta(days=index), 100.0) for index in range(40)], DAY))

    def test_news_surge_compares_the_last_day_with_the_day_before(self) -> None:
        self.assertEqual(news_surge(moments(30, 10), NOW, True), 3.0)
        self.assertEqual(news_surge(moments(12, 0), NOW, True), 12.0)
        self.assertIsNone(news_surge(moments(30, 10), NOW, False))
        self.assertIsNone(news_surge(moments(4, 5), NOW, True))
        naive = [moment.replace(tzinfo=None) for moment in moments(30, 10)]
        self.assertIsNone(news_surge(naive + ["yesterday", None, NOW + timedelta(hours=1)], NOW, True))

    def test_naver_lookup_pages_until_two_days_are_covered_and_stops_on_errors(self) -> None:
        calls: list = []
        rows = sorted(moments(150, 60, older=20), reverse=True)
        lookup = naver_news("client", "secret", get=pages(rows, calls), clock=lambda: NOW)
        self.assertEqual(lookup({"ticker": "005380.KS", "company_name": "현대자동차"}), 2.5)
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[0][0], NEWS_URL)
        self.assertEqual(calls[0][1], {"query": "현대차 주가", "display": 100, "start": 1, "sort": "date"})
        self.assertEqual(calls[0][2], {"X-NCP-APIGW-API-KEY-ID": "client", "X-NCP-APIGW-API-KEY": "secret"})
        # A thousand articles inside two days cannot be compared; a short complete list can.
        other = {"ticker": "X", "company_name": "X"}
        dense = [NOW - timedelta(minutes=index) for index in range(1000)]
        self.assertIsNone(naver_news("c", "s", get=pages(dense, []), clock=lambda: NOW)(other))
        few = sorted(moments(8, 4, older=0), reverse=True)
        self.assertEqual(naver_news("c", "s", get=pages(few, []), clock=lambda: NOW)(other), 2.0)
        calls.clear()
        self.assertIsNone(naver_news("c", "s", get=pages(rows, calls, 401), clock=lambda: NOW)(other))
        self.assertEqual((len(calls), calls[0][1]["query"]), (1, "X 주가"))

    def test_scores_combine_available_signals_and_survive_source_failures(self) -> None:
        self.assertEqual(combine(8, None), 1.0)
        self.assertEqual(combine(2, 4), 0.75)
        self.assertIsNone(combine(None, None))
        profiles = [{"company_name": name, "ticker": name} for name in ("A", "B", "C")]

        def price(ticker: str) -> list[tuple[date, float]]:
            if ticker == "B":
                raise RuntimeError("market data unavailable")
            return closes(0.05 if ticker == "A" else 0.01)

        def news(profile: dict) -> float | None:
            if profile["ticker"] == "C":
                raise RuntimeError("news unavailable")
            return 3.0

        scores = attention_scores(profiles, DAY, closes=price, news=news)
        self.assertEqual(scores["A"]["score"], 0.875)
        self.assertEqual(scores["B"], {"price_move": None, "news_surge": 3.0, "score": 0.75})
        self.assertIsNone(scores["C"]["news_surge"])
        alone = attention_scores(profiles[:1], DAY, closes=price)["A"]
        self.assertEqual((alone["news_surge"], alone["score"]), (None, 1.0))
        self.assertIsNone(attention_scores(profiles[1:2], DAY, closes=price)["B"]["score"])


if __name__ == "__main__":
    unittest.main()
