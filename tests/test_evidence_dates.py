from datetime import date, datetime, timezone
import unittest

from app.regime_workflow import RegimeWorkflow
from tools.evidence_dates import parse_evidence_date


class EvidenceDateTests(unittest.TestCase):
    def test_calendar_and_dart_dates_are_preserved(self) -> None:
        for value in ("2026-08-21", "20260821", " 20260821 ", date(2026, 8, 21)):
            with self.subTest(value=value):
                self.assertEqual(parse_evidence_date(value), date(2026, 8, 21))
        self.assertEqual(parse_evidence_date("20240229"), date(2024, 2, 29))

    def test_aware_timestamps_use_korean_calendar_day(self) -> None:
        for value, expected in [
            ("2026-10-14T14:59:59Z", date(2026, 10, 14)),
            ("2026-10-14T15:00:00Z", date(2026, 10, 15)),
            ("2026-10-14T15:30:00+00:00", date(2026, 10, 15)),
            ("2026-10-15T00:30:00+14:00", date(2026, 10, 14)),
            ("2026-10-15T00:30:00+0900", date(2026, 10, 15)),
            ("2026-10-14 15:30:00.123456z", date(2026, 10, 15)),
            (datetime(2026, 10, 14, 15, tzinfo=timezone.utc), date(2026, 10, 15)),
        ]:
            with self.subTest(value=value):
                self.assertEqual(parse_evidence_date(value), expected)
                self.assertEqual(RegimeWorkflow._date(value), expected)

    def test_invalid_or_ambiguous_values_are_not_truncated_or_guessed(self) -> None:
        for value in (None, "", 20261015, "2026-2-15", "20260229", "2026-02-30", "2026-13-01", "2026-10", "2026-10-15invalid", "2026-10-15T25:00:00Z", "2026-10-15Q00:00:00Z", "2026-10-15T00:00:00+25:00", "2026-10-15T00:00:00", datetime(2026, 10, 15)):
            with self.subTest(value=value):
                self.assertIsNone(parse_evidence_date(value))
                self.assertIsNone(RegimeWorkflow._date(value))

    def catalog(self) -> list[dict]:
        return [
            {"source_id": source_id, "published_at": published, "title": source_id,
             "content": "Reported evidence.", "quotes": [{"quote_id": source_id + "-Q01", "text": "Reported evidence."}],
             "source_url": "https://example.com/report"}
            for source_id, published in [("DART-001", "20261015"), ("UTC-001", "2026-10-14T15:30:00Z"), ("BAD-001", "2026-10-15invalid")]
        ]

    def test_dart_and_utc_evidence_reach_only_matching_regime_candidates(self) -> None:
        analysis = {"regimes": {
            "past_bull": {"start_date": "2026-10-14", "end_date": "2026-10-14"},
            "recent_bear": {"start_date": "2026-10-15", "end_date": "2026-10-15"},
        }}
        candidates = RegimeWorkflow._candidates(analysis, self.catalog())
        self.assertEqual(candidates["past_bull"], [])
        self.assertEqual([item["source_id"] for item in candidates["recent_bear"]], ["DART-001", "UTC-001"])
        self.assertEqual({item["published_at"] for item in candidates["recent_bear"]}, {"2026-10-15"})

    def test_timeline_and_price_reaction_use_normalized_evidence_date(self) -> None:
        timeline = RegimeWorkflow._timeline_evidence({"recent_daily": [
            {"period": "2026-10-14", "start_date": "2026-10-14", "end_date": "2026-10-14"},
            {"period": "2026-10-15", "start_date": "2026-10-15", "end_date": "2026-10-15"},
        ]}, self.catalog(), [
            {"date": "2026-10-14", "close": 80},
            {"date": "2026-10-15", "close": 100},
            {"date": "2026-10-16", "close": 102},
        ], [])
        self.assertEqual(timeline["recent_daily"]["2026-10-14"], [])
        evidence = timeline["recent_daily"]["2026-10-15"]
        self.assertEqual([item["source_id"] for item in evidence], ["DART-001", "UTC-001"])
        self.assertTrue(all(item["verified"] for item in evidence))
        self.assertEqual({item["event_date"] for item in evidence}, {"2026-10-15"})
        self.assertEqual({item["price_reaction_1d_pct"] for item in evidence}, {2.0})


if __name__ == "__main__":
    unittest.main()
