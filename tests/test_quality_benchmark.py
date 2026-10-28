"""Synthetic local regression cases; these are not service accuracy benchmarks."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.quality_benchmark import export_review_queue, evaluate_quality, validate_queue, main


class QualityBenchmarkTests(unittest.TestCase):
    def result(self) -> dict:
        return {
            "analysis_as_of": "2026-10-15", "api_key": "private-key-never-copy", "owner": "private@example.com",
            "evidence_catalog": [{"source_id": "S1", "source_url": "https://private.example/article", "published_at": "2026-10-01",
                "content": "매출이 30% 증가했다. 원문 전체의 비공개 내용.", "quotes": [{"quote_id": "Q1", "text": "매출이 30% 증가했다."}]}],
            "rounds": [{"bull_response": {"issues": [{"claim": "매출이 30% 감소했다.", "evidence": [{"source_id": "S1", "quote_id": "Q1", "exact_quote": "매출이 30% 증가했다."}]}]},
                        "bear_response": {"issues": [{"claim": "매출이 15% 증가했다.", "evidence": [{"source_id": "S1", "quote_id": "Q1"}]}]}}],
        }

    def queue(self) -> dict:
        return export_review_queue(self.result(), "synthetic")

    def predictions(self, data: dict, labels: list, origin: str = "model") -> dict:
        return {"schema_version": 1, "origin": origin, "private_prompt": "never export this prompt", "cases": [
            {"case_id": case["case_id"], "input_hash": case["input_hash"], "label": label}
            for case, label in zip(data["cases"], labels)]}

    def test_export_is_local_excerpt_queue_not_complete_result_or_semantic_judgment(self) -> None:
        original = self.result()
        before = copy.deepcopy(original)
        queue = export_review_queue(original)
        self.assertEqual(queue["dataset_kind"], "real")
        self.assertEqual(queue["cases"][0]["review"], {"origin": "unreviewed", "label": None})
        self.assertEqual(queue["cases"][0]["input"]["evidence"][0]["text"], "매출이 30% 증가했다.")
        self.assertEqual(queue["cases"][0]["input"]["checks"]["numeric_status"], "values_present")
        self.assertEqual(queue["cases"][1]["input"]["checks"]["numeric_status"], "needs_review")
        encoded = json.dumps(queue, ensure_ascii=False)
        for secret in ("private-key-never-copy", "private@example.com", "원문 전체의 비공개 내용", "semantic_status"):
            self.assertNotIn(secret, encoded)
        self.assertEqual(original, before)

    def test_unreviewed_inputs_have_no_fake_accuracy(self) -> None:
        data = self.queue()
        report = evaluate_quality(data)
        self.assertEqual(report["kind"], "rag")
        self.assertEqual(report["scope"], "answer_quality")
        self.assertEqual(report["settings"]["dataset_kind"], "synthetic")
        self.assertEqual(report["settings"]["semantic_status"], "not_evaluated")
        self.assertIsNone(report["metrics"]["semantic_accuracy"])
        self.assertEqual(report["metrics"]["reviewed_count"], 0)
        self.assertEqual(report["metrics"]["review_coverage"], 0)
        self.assertEqual(report["metrics"]["numeric_review_count"], 1)

    def test_human_reference_comparison_and_confusion_counts(self) -> None:
        data = self.queue()
        for case, label in zip(data["cases"], ("contradicted", "insufficient_evidence")):
            case["review"] = {"origin": "human", "label": label}
        predictions = self.predictions(data, ["contradicted", "supported"])
        report = evaluate_quality(data, predictions)
        metrics = report["metrics"]
        self.assertEqual(metrics["semantic_accuracy"], .5)
        self.assertEqual(metrics["reviewed_count"], 2)
        self.assertEqual(metrics["compared_count"], 2)
        self.assertEqual(metrics["prediction_count"], 2)
        self.assertEqual(metrics["review_coverage"], 1)
        self.assertEqual(metrics["confusion_contradicted_contradicted"], 1)
        self.assertEqual(metrics["confusion_insufficient_evidence_supported"], 1)
        self.assertEqual(sum(v for k, v in metrics.items() if k.startswith("confusion_")), 2)
        self.assertEqual([row["correct"] for row in report["cases"]], [1, 0])
        self.assertEqual(report["settings"]["prediction_origin"], "model")

    def test_model_annotations_are_not_promoted_to_human_gold(self) -> None:
        data = self.queue()
        for case in data["cases"]:
            case["review"] = {"origin": "model", "label": "supported"}
        report = evaluate_quality(data, self.predictions(data, ["supported", "supported"]))
        self.assertEqual(report["settings"]["annotation_origin"], "model")
        self.assertEqual(report["metrics"]["prediction_count"], 2)
        self.assertEqual(report["metrics"]["reviewed_count"], 0)
        self.assertEqual(report["metrics"]["compared_count"], 0)
        self.assertIsNone(report["metrics"]["semantic_accuracy"])

    def test_partial_human_review_and_predictions_are_denominator_explicit(self) -> None:
        data = self.queue()
        data["cases"][0]["review"] = {"origin": "human", "label": "contradicted"}
        report = evaluate_quality(data, self.predictions(data, [None, "supported"]))
        self.assertEqual(report["settings"]["annotation_origin"], "mixed")
        self.assertEqual(report["metrics"]["review_coverage"], .5)
        self.assertEqual(report["metrics"]["prediction_count"], 1)
        self.assertEqual(report["metrics"]["compared_count"], 0)
        self.assertIsNone(report["metrics"]["semantic_accuracy"])

    def test_report_contains_no_claims_quotes_urls_custom_names_or_prompts(self) -> None:
        data = self.queue(); data["name"] = "private@example.com"
        data["cases"][0]["review"] = {"origin": "human", "label": "contradicted", "reason": "private reviewer notes"}
        predictions = self.predictions(data, ["supported"])
        report = evaluate_quality(data, predictions)
        encoded = json.dumps(report, ensure_ascii=False)
        for secret in ("매출", "private.example", "source_url", "statements", "private@example.com", "private reviewer notes", "never export this prompt"):
            self.assertNotIn(secret, encoded)
        self.assertEqual(report["label"], "Claim-evidence support")
        self.assertEqual(len(report["dataset_hash"]), 64)
        self.assertEqual(len(report["settings"]["predictions_hash"]), 64)

    def test_evaluation_does_not_mutate_or_loses_case_hashes(self) -> None:
        data = self.queue(); predictions = self.predictions(data, ["contradicted"])
        before = copy.deepcopy((data, predictions))
        report = evaluate_quality(data, predictions)
        self.assertEqual((data, predictions), before)
        self.assertEqual(report["cases"][0]["input_hash"], data["cases"][0]["input_hash"])
        self.assertEqual(evaluate_quality(data, predictions)["dataset_hash"], report["dataset_hash"])

    def test_changed_input_unknown_cases_duplicates_and_wrong_hash_fail(self) -> None:
        data = self.queue()
        changed = copy.deepcopy(data); changed["cases"][0]["input"]["statements"]["claim"] = "변경된 주장"
        with self.assertRaises(ValueError): evaluate_quality(changed)
        for modify in (
            lambda p: p["cases"][0].update(case_id="C-999999"),
            lambda p: p["cases"][0].update(case_id=[]),
            lambda p: p["cases"][0].update(input_hash="0"*64),
            lambda p: p["cases"].append(copy.deepcopy(p["cases"][0])),
            lambda p: p["cases"][0].update(label="definitely true"),
            lambda p: p.update(origin="unreviewed"),
        ):
            predictions = self.predictions(data, ["supported"]); modify(predictions)
            with self.assertRaises(ValueError): evaluate_quality(data, predictions)

    def test_untrusted_review_ids_and_labels_cannot_leak_into_reports(self) -> None:
        for field, value in (("case_id", "private@example.com"), ("review", {"origin": "private@example.com", "label": None}), ("review", {"origin": "human", "label": "private explanation"}), ("review", {"origin": "unreviewed", "label": "supported"})):
            data = self.queue(); data["cases"][0][field] = value
            with self.assertRaises(ValueError): evaluate_quality(data)
        data = self.queue(); data["cases"].append(copy.deepcopy(data["cases"][0]))
        with self.assertRaises(ValueError): validate_queue(data)

    def test_invalid_and_empty_datasets_never_generate_scores(self) -> None:
        for data in ({}, {"schema_version": 1, "dataset_kind": "real", "cases": []}, {"schema_version": 1, "dataset_kind": "other", "cases": []}):
            with self.assertRaises(ValueError): evaluate_quality(data)
        with self.assertRaises(ValueError): export_review_queue({"rounds": []})

    def test_rule_flags_are_booleans_and_reconstruct_each_summary_count(self) -> None:
        data = self.queue()
        report = evaluate_quality(data)
        for flag, metric in (("numeric_review", "numeric_review_count"), ("identity_invalid", "identity_invalid_count"), ("future_source", "future_source_count")):
            self.assertTrue(all(type(row[flag]) is bool for row in report["cases"]))
            self.assertEqual(sum(row[flag] for row in report["cases"]), report["metrics"][metric])
        self.assertEqual([row["numeric_review"] for row in report["cases"]], [False, True])
        changed = copy.deepcopy(report)
        changed["metrics"]["numeric_review_count"] = 0
        self.assertNotEqual(sum(row["numeric_review"] for row in changed["cases"]), changed["metrics"]["numeric_review_count"])

    def test_missing_identity_and_future_source_counts_are_case_counts(self) -> None:
        result = self.result()
        result["evidence_catalog"][0]["published_at"] = "2026-10-16"
        result["rounds"][0]["bear_response"]["issues"][0]["evidence"][0]["source_id"] = "missing"
        report = evaluate_quality(export_review_queue(result, "synthetic"))
        self.assertEqual(report["metrics"]["future_source_count"], 1)
        self.assertEqual(report["metrics"]["identity_invalid_count"], 1)

    def test_cli_export_then_evaluate_preserves_existing_output(self) -> None:
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary); source=folder/"source.json"; queue=folder/"queue.json"; report=folder/"report.json"
            source.write_text(json.dumps(self.result(), ensure_ascii=False), encoding="utf-8")
            with patch("sys.argv", ["quality", "export", str(source), "--output", str(queue), "--dataset-kind", "synthetic"]): main()
            with patch("sys.argv", ["quality", "evaluate", str(queue), "--output", str(report)]): main()
            value=report.read_text(encoding="utf-8")
            self.assertIsNone(json.loads(value)["metrics"]["semantic_accuracy"])
            with patch("sys.argv", ["quality", "evaluate", str(queue), "--output", str(report)]), self.assertRaises(SystemExit): main()
            self.assertEqual(report.read_text(encoding="utf-8"), value)


if __name__ == "__main__":
    unittest.main()
