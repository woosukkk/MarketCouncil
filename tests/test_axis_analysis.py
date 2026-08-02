import tempfile
import unittest
from pathlib import Path

from agents.analysis_axes import select_analysis_axes
from agents.axis_analysis_schema import normalize_perspective_analysis
from agents.axis_judgment import compare_axis_judgments, normalize_axis_judgment
from tools.axis_analysis_store import AxisAnalysisStore
from tools.markdown_report_renderer import MarkdownReportRenderer


class AnalysisAxesTest(unittest.TestCase):
    def test_semiconductor_axes_are_added_and_weights_sum_to_one(self) -> None:
        axes = select_analysis_axes("삼성전자", {"ticker": "005930.KS"})
        axis_ids = {axis["id"] for axis in axes}
        self.assertIn("industry_cycle", axis_ids)
        self.assertIn("supply_chain", axis_ids)
        self.assertIn("policy_environment", axis_ids)
        self.assertAlmostEqual(sum(axis["weight"] for axis in axes), 1.0, places=5)

    def test_non_semiconductor_uses_base_axes(self) -> None:
        axes = select_analysis_axes("현대자동차", {"ticker": "005380.KS"})
        self.assertNotIn("industry_cycle", {axis["id"] for axis in axes})


class PerspectiveNormalizationTest(unittest.TestCase):
    def test_unknown_axis_and_evidence_are_rejected(self) -> None:
        axes = select_analysis_axes("현대자동차", {"ticker": "005380.KS"})
        raw = {
            "role": "bull",
            "axis_results": [
                {
                    "axis_id": "earnings_outlook",
                    "status": "available",
                    "direction": 2,
                    "summary": "개선",
                    "verified_facts": ["이익 증가"],
                    "market_expectations": [],
                    "analyst_hypotheses": [],
                    "evidence_refs": ["invented.ref"],
                    "confidence": "high",
                    "counter_conditions": [],
                    "unavailable_reason": "",
                },
                {"axis_id": "unknown", "status": "available", "direction": 2},
            ],
        }
        result = normalize_perspective_analysis(
            raw, "bull", axes, {"financial.operating_income_growth"}
        )
        earnings = next(
            item for item in result["axis_results"]
            if item["axis_id"] == "earnings_outlook"
        )
        self.assertEqual(earnings["status"], "unavailable")
        self.assertEqual(earnings["direction"], 0)
        self.assertNotIn("unknown", {item["axis_id"] for item in result["axis_results"]})

    def test_role_direction_is_enforced(self) -> None:
        axes = select_analysis_axes("현대자동차", {"ticker": "005380.KS"})
        raw = {
            "axis_results": [{
                "axis_id": "earnings_outlook",
                "status": "available",
                "direction": 2,
                "summary": "잘못된 방향",
                "verified_facts": [],
                "market_expectations": [],
                "analyst_hypotheses": [],
                "evidence_refs": [],
                "confidence": "medium",
                "counter_conditions": [],
                "unavailable_reason": "",
            }]
        }
        result = normalize_perspective_analysis(raw, "bear", axes)
        earnings = next(item for item in result["axis_results"] if item["axis_id"] == "earnings_outlook")
        self.assertEqual(earnings["direction"], 0)


class JudgmentTest(unittest.TestCase):
    def test_aggregation_distinguishes_unavailable_from_neutral(self) -> None:
        axes = select_analysis_axes("현대자동차", {"ticker": "005380.KS"})
        raw = {
            "axis_judgments": [{
                "axis_id": "earnings_outlook",
                "status": "available",
                "verdict": 2,
                "confidence": "high",
                "reason": "실적 개선",
                "bull_evidence_refs": ["financial.operating_income_growth"],
                "bear_evidence_refs": [],
                "strengthening_conditions": [],
                "weakening_conditions": [],
                "invalidation_conditions": [],
            }],
            "evidence_limitations": ["거시 데이터 부족"],
            "conditional_conclusion": "실적 개선이 지속되면 가설이 강화된다.",
        }
        result = normalize_axis_judgment(
            raw,
            axes,
            {"financial.operating_income_growth"},
            {"earnings_outlook"},
        )
        overall = result["overall"]
        self.assertGreater(overall["bull_score"], 50)
        self.assertLess(overall["bull_score"], 70)
        self.assertLess(overall["evidence_coverage"], 0.5)
        self.assertEqual(overall["rating"], "Neutral")

    def test_change_tracking_reports_only_changed_axes(self) -> None:
        axes = select_analysis_axes("현대자동차", {"ticker": "005380.KS"})
        current = {"axis_judgments": [{
            "axis_id": "earnings_outlook", "status": "available", "verdict": 1
        }]}
        previous = {"axis_judgments": [{
            "axis_id": "earnings_outlook", "status": "available", "verdict": -1
        }]}
        changes = compare_axis_judgments(current, previous, axes)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["previous_verdict"], -1)
        self.assertEqual(changes[0]["current_verdict"], 1)


class StorageAndRenderingTest(unittest.TestCase):
    def test_store_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = AxisAnalysisStore(Path(directory))
            store.save("테스트 기업", {"schema_version": "1.0", "axis_judgments": []})
            loaded = store.load_latest("테스트 기업")
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded["schema_version"], "1.0")

    def test_markdown_contains_axis_table(self) -> None:
        axes = select_analysis_axes("현대자동차", {"ticker": "005380.KS"})
        judgments = [
            {
                "axis_id": axis["id"],
                "status": "unavailable",
                "verdict": 0,
                "confidence": "low",
                "reason": "확인 불가",
            }
            for axis in axes
        ]
        markdown = MarkdownReportRenderer().render({
            "company_name": "현대자동차",
            "analysis_axes": axes,
            "axis_judgment": {
                "axis_judgments": judgments,
                "overall": {
                    "rating": "Neutral",
                    "bull_score": 50,
                    "bear_score": 50,
                    "confidence": "Low",
                    "evidence_coverage": 0,
                },
            },
            "judge_result": "# 최종 판단\n- Final Rating: Neutral",
        })
        self.assertIn("## 분석 축별 판단", markdown)
        self.assertIn("확인 불가", markdown)


if __name__ == "__main__":
    unittest.main()
