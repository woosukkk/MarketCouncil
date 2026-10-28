"""Retrieval leakage checks must use the same KST cutoff as ReportRetriever."""
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from tools.rag_benchmark import score


class AwareTimestampRequired(datetime):
    def timestamp(self) -> float:
        if self.tzinfo is None:
            raise AssertionError("A host-local cutoff cannot define a KST benchmark")
        return super().timestamp()


class RagBenchmarkDatesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.case = {"as_of_date": "2026-10-15", "company": "Example", "expected": [{"source": "one"}]}

    def test_kst_midnight_boundary_is_host_timezone_independent(self) -> None:
        rows = [{"source": "one", "metadata": {"company": "Example", "published_timestamp": datetime(2026, 10, 15, 14, 59, 59, tzinfo=timezone.utc).timestamp()}},
                {"source": "later", "metadata": {"company": "Example", "published_timestamp": datetime(2026, 10, 15, 15, 0, 0, tzinfo=timezone.utc).timestamp()}}]
        with patch("tools.rag_benchmark.datetime", AwareTimestampRequired):
            result = score(self.case, rows)
        self.assertEqual(result["future_sources"], 1)
        self.assertEqual(result["recall"], 1)

    def test_cutoff_day_utc_afternoon_is_already_next_kst_day(self) -> None:
        rows = [{"source": "one", "metadata": {"company": "Example", "published_timestamp": datetime(2026, 10, 15, 20, tzinfo=timezone.utc).timestamp()}}]
        self.assertEqual(score(self.case, rows)["future_sources"], 1)


if __name__ == "__main__":
    unittest.main()
