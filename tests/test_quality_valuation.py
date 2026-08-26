import unittest

from tools.quality_valuation import calculate_quality_metrics


class QualityValuationTest(unittest.TestCase):
    def test_calculates_shared_quality_metrics(self) -> None:
        facts = {
            "market_cap": 1_000.0,
            "annual_history": [
                {
                    "revenue": 120.0,
                    "operating_margin": 0.20,
                    "net_income": 20.0,
                    "free_cash_flow": 18.0,
                    "total_debt": 30.0,
                    "stockholders_equity": 100.0,
                    "shares_outstanding": 90.0,
                },
                {
                    "revenue": 110.0,
                    "operating_margin": 0.18,
                    "net_income": 18.0,
                    "free_cash_flow": 15.0,
                    "shares_outstanding": 95.0,
                },
                {
                    "revenue": 100.0,
                    "operating_margin": 0.17,
                    "net_income": 15.0,
                    "free_cash_flow": 12.0,
                    "shares_outstanding": 100.0,
                },
            ],
        }

        result = calculate_quality_metrics(facts)

        self.assertEqual(result["normalized_fcf"], 15.0)
        self.assertEqual(result["fcf_yield"], 0.015)
        self.assertEqual(result["positive_fcf_ratio"], 1.0)
        self.assertEqual(result["debt_to_equity"], 0.3)
        self.assertAlmostEqual(result["dilution_rate"], -0.1)
        self.assertEqual(result["missing_inputs"], [])

    def test_reports_missing_inputs_instead_of_estimating(self) -> None:
        result = calculate_quality_metrics({
            "market_cap": None,
            "annual_history": [{"revenue": 100.0}],
        })

        self.assertIsNone(result["normalized_fcf"])
        self.assertIsNone(result["fcf_yield"])
        self.assertIn("시가총액", result["missing_inputs"])
        self.assertIn(
            "3개년 이상 잉여현금흐름",
            result["missing_inputs"],
        )


if __name__ == "__main__":
    unittest.main()
