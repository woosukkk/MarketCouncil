import unittest

from app.web_app import extract_metrics, score_split, validate_company_name


class WebAppTest(unittest.TestCase):
    def test_company_name_validation(self) -> None:
        self.assertEqual(validate_company_name(" 삼성전자 "), "삼성전자")
        with self.assertRaises(ValueError):
            validate_company_name("A")

    def test_extracts_judge_metrics(self) -> None:
        result = extract_metrics(
            "- Final Rating: Moderate Bull\n"
            "- Bull Score: 62\n"
            "- Bear Score: 38\n"
            "- Confidence: Medium"
        )
        self.assertEqual(result["rating"], "Moderate Bull")
        self.assertEqual(result["bull"], "62")
        self.assertEqual(result["bear"], "38")
        self.assertEqual(result["confidence"], "Medium")

    def test_normalizes_bull_bear_scores(self) -> None:
        self.assertEqual(score_split("62", "38"), (62, 38))
        self.assertEqual(score_split("—", "—"), (50, 50))
        self.assertEqual(score_split("0", "0"), (50, 50))


if __name__ == "__main__":
    unittest.main()
