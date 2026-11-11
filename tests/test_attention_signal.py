"""Synthetic numbers only; no network, market data or search service."""
import unittest
from datetime import date, timedelta

from tools.attention_signal import attention_scores, combine, news_surge, price_move

DAY = date(2026, 11, 3)


def closes(last_move: float, days: int = 40) -> list[tuple[date, float]]:
    values, price = [], 100.0
    for index in range(days):
        price *= 1.01 if index % 2 else 0.99
        values.append((DAY - timedelta(days=days - index), price))
    values.append((DAY, price * (1 + last_move)))
    return values


def stamps(recent: int, earlier: int) -> list[str]:
    rows = [(DAY - timedelta(days=index % 2)).isoformat() + "T09:00:00+09:00" for index in range(recent)]
    rows += [(DAY - timedelta(days=2 + index % 5)).isoformat() + "T09:00:00+09:00" for index in range(earlier)]
    return rows


class AttentionSignalTests(unittest.TestCase):
    def test_price_move_is_relative_to_own_volatility_and_ignores_later_dates(self) -> None:
        calm, sharp = price_move(closes(0.01), DAY), price_move(closes(0.05), DAY)
        self.assertAlmostEqual(calm, 1.0, delta=0.15)
        self.assertGreater(sharp, 4)
        self.assertEqual(price_move(closes(0.05) + [(DAY + timedelta(days=1), 500.0)], DAY), sharp)
        self.assertIsNone(price_move(closes(0.05, days=10), DAY))
        self.assertIsNone(price_move([(DAY - timedelta(days=index), 100.0) for index in range(40)], DAY))

    def test_news_surge_compares_recent_days_with_the_earlier_week(self) -> None:
        self.assertAlmostEqual(news_surge(stamps(4, 10), DAY), 1.0)
        self.assertAlmostEqual(news_surge(stamps(12, 10), DAY), 3.0)
        self.assertIsNone(news_surge(stamps(2, 2), DAY))
        undated = ["", "2026-11-03 09:00", None, "yesterday", (DAY + timedelta(days=1)).isoformat() + "T00:00:00+09:00"]
        self.assertIsNone(news_surge(undated * 3, DAY))
        # 2026-11-02T16:00Z is 2026-11-03 in Korea.
        self.assertAlmostEqual(news_surge(["2026-11-02T16:00:00Z"] * 4 + stamps(0, 10), DAY), 1.0)

    def test_scores_combine_available_signals_and_survive_source_failures(self) -> None:
        self.assertEqual(combine(8, None), 1.0)
        self.assertEqual(combine(2, 4), 0.75)
        self.assertIsNone(combine(None, None))
        profiles = [{"company_name": "A", "ticker": "A"}, {"company_name": "B", "ticker": "B"}, {"company_name": "C", "ticker": "C"}]

        def price(ticker: str) -> list[tuple[date, float]]:
            if ticker == "B":
                raise RuntimeError("market data unavailable")
            return closes(0.05 if ticker == "A" else 0.01)

        def news(profile: dict, url: str) -> list[str]:
            if profile["ticker"] == "C":
                raise RuntimeError("search unavailable")
            return stamps(12, 10)

        scores = attention_scores(profiles, DAY, "http://127.0.0.1:8080", closes=price, news_dates=news)
        self.assertEqual(scores["A"]["score"], 0.875)
        self.assertEqual((scores["B"]["price_move"], scores["B"]["score"]), (None, 0.75))
        self.assertIsNone(scores["C"]["news_surge"])
        without_search = attention_scores(profiles[:1], DAY, None, closes=price, news_dates=news)
        self.assertEqual((without_search["A"]["news_surge"], without_search["A"]["score"]), (None, 1.0))
        failed = attention_scores(profiles[1:2], DAY, None, closes=price, news_dates=news)
        self.assertIsNone(failed["B"]["score"])


if __name__ == "__main__":
    unittest.main()
