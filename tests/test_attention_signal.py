"""Synthetic numbers only; no network or market data."""
import unittest
from datetime import date, timedelta

from tools.attention_signal import attention_scores, price_move

DAY = date(2026, 11, 3)


def closes(last_move: float, days: int = 40) -> list[tuple[date, float]]:
    values, price = [], 100.0
    for index in range(days):
        price *= 1.01 if index % 2 else 0.99
        values.append((DAY - timedelta(days=days - index), price))
    values.append((DAY, price * (1 + last_move)))
    return values


class AttentionSignalTests(unittest.TestCase):
    def test_price_move_is_relative_to_own_volatility_and_ignores_later_dates(self) -> None:
        calm, sharp = price_move(closes(0.01), DAY), price_move(closes(0.05), DAY)
        self.assertAlmostEqual(calm, 1.0, delta=0.15)
        self.assertGreater(sharp, 4)
        self.assertAlmostEqual(price_move(closes(-0.05), DAY), sharp, delta=0.5)
        self.assertEqual(price_move(closes(0.05) + [(DAY + timedelta(days=1), 500.0)], DAY), sharp)
        self.assertIsNone(price_move(closes(0.05, days=10), DAY))
        self.assertIsNone(price_move([(DAY - timedelta(days=index), 100.0) for index in range(40)], DAY))

    def test_scores_are_capped_and_survive_lookup_failures(self) -> None:
        profiles = [{"company_name": name, "ticker": name} for name in ("A", "B", "C")]

        def price(ticker: str) -> list[tuple[date, float]]:
            if ticker == "B":
                raise RuntimeError("market data unavailable")
            return closes(0.05 if ticker == "A" else 0.01)

        scores = attention_scores(profiles, DAY, closes=price)
        self.assertEqual(scores["A"]["score"], 1.0)
        self.assertEqual(scores["B"], {"price_move": None, "score": None})
        self.assertAlmostEqual(scores["C"]["score"], 0.25, delta=0.04)
        self.assertEqual(set(scores["A"]), {"price_move", "score"})


if __name__ == "__main__":
    unittest.main()
