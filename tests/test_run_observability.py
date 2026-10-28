"""Offline instrumentation contracts; never call providers or load real keys."""
import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from pathlib import Path
from types import SimpleNamespace as NS
from typing import TypedDict
from unittest.mock import Mock, patch

from tools.analysis_checkpoint import AnalysisCheckpoint
from tools.run_metrics import create_response, measure_analysis, measure_stage


PRICING = {"model": "gpt-offline-test", "currency": "USD", "source": "manual", "as_of": "2026-10-27",
           "input_per_million": 1.0, "cached_input_per_million": .1, "output_per_million": 2.0}


def response(input_tokens: int = 100, output_tokens: int = 10, cached: int = 25, reasoning: int = 4) -> NS:
    return NS(status="completed", output_text="private-answer-marker", usage=NS(
        input_tokens=input_tokens, output_tokens=output_tokens,
        input_tokens_details=NS(cached_tokens=cached),
        output_tokens_details=NS(reasoning_tokens=reasoning)))


def client(*responses: object) -> NS:
    return NS(responses=NS(create=Mock(side_effect=responses)))


def invoke(fake: NS, phase: str = "bull_initial", **kwargs: object) -> object:
    return create_response(fake, phase, model="gpt-offline-test", input="private-input-marker", **kwargs)


class RunObservabilityTests(unittest.TestCase):
    def report(self, callback, *, pricing: dict | None = PRICING) -> tuple[object, dict]:
        with tempfile.TemporaryDirectory() as folder:
            value = measure_analysis("Example", callback, Path(folder), pricing=pricing)
            report = json.loads(next(Path(folder).glob("*.json")).read_text(encoding="utf-8"))
            return value, report

    def test_response_identity_usage_price_and_phase_are_preserved(self) -> None:
        original = response()
        fake = client(original)
        value, report = self.report(lambda: invoke(fake))
        self.assertIs(value, original)
        fake.responses.create.assert_called_once_with(model="gpt-offline-test", input="private-input-marker")
        llm = report["llm"]
        self.assertEqual((llm["request_count"], llm["usage_known_calls"], llm["usage_missing_calls"]), (1, 1, 0))
        self.assertEqual((llm["input_tokens"], llm["output_tokens"], llm["cached_input_tokens"], llm["reasoning_tokens"]), (100, 10, 25, 4))
        self.assertAlmostEqual(llm["estimated_cost_usd"], (75 + 25 * .1 + 10 * 2) / 10**6)
        self.assertEqual(llm["cost_status"], "estimated")
        self.assertEqual(llm["coverage"], "observed_responses_only")
        self.assertFalse(llm["sdk_retries_included"])
        self.assertFalse(llm["tool_costs_included"])
        phase = llm["by_phase"][0]
        self.assertEqual(phase["phase"], "bull_initial")
        self.assertEqual(phase["input_tokens"], llm["input_tokens"])
        self.assertGreaterEqual(phase["duration_ms"], 0)
        text = json.dumps(report)
        self.assertNotIn("private-input-marker", text)
        self.assertNotIn("private-answer-marker", text)

    def test_exception_is_unchanged_and_unknown_usage_is_not_zero_cost(self) -> None:
        original = RuntimeError("private-error-marker")
        fake = client(original)
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(RuntimeError) as caught:
                measure_analysis("Example", lambda: invoke(fake), Path(folder), pricing=PRICING)
            self.assertIs(caught.exception, original)
            report = json.loads(next(Path(folder).glob("*.json")).read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["llm"]["error_count"], 1)
        self.assertEqual(report["llm"]["usage_missing_calls"], 1)
        for key in ("input_tokens", "output_tokens", "estimated_cost_usd"):
            self.assertIsNone(report["llm"][key])
        self.assertEqual(report["llm"]["cost_status"], "unavailable")
        self.assertNotIn("private-error-marker", json.dumps(report))

    def test_no_observed_calls_has_no_invented_zero_usage_or_cost(self) -> None:
        value, report = self.report(lambda: 42)
        self.assertEqual(value, 42)
        self.assertEqual(report["llm"]["request_count"], 0)
        self.assertIsNone(report["llm"]["estimated_cost_usd"])
        self.assertIsNone(report["llm"]["input_tokens"])
        self.assertEqual(report["llm"]["by_phase"], [])

    def test_partial_usage_aggregates_only_observed_totals(self) -> None:
        fake = client(response(), NS(status="completed", output_text="private"))
        def run():
            invoke(fake)
            return invoke(fake, "bear_initial")
        _, report = self.report(run)
        llm = report["llm"]
        self.assertEqual((llm["request_count"], llm["usage_known_calls"], llm["usage_missing_calls"]), (2, 1, 1))
        self.assertEqual(llm["input_tokens"], 100)
        self.assertEqual(llm["cost_status"], "partial")
        self.assertIsNone(llm["cached_input_tokens"])
        self.assertIsNone(llm["reasoning_tokens"])
        self.assertEqual(sum(row["request_count"] for row in llm["by_phase"]), llm["request_count"])
        self.assertEqual(sum(row["estimated_cost_usd"] or 0 for row in llm["by_phase"]), llm["estimated_cost_usd"])

    def test_incomplete_response_is_returned_and_counted_as_an_unsuccessful_call(self) -> None:
        original = response()
        original.status = "incomplete"
        value, report = self.report(lambda: invoke(client(original)))
        self.assertIs(value, original)
        self.assertEqual(report["llm"]["error_count"], 1)
        self.assertEqual(report["llm"]["input_tokens"], 100)
        self.assertIsNotNone(report["llm"]["estimated_cost_usd"])

    def test_missing_or_inconsistent_details_never_get_assumed_zero(self) -> None:
        for mutation in ("missing_cache", "too_much_cache", "too_much_reasoning", "negative_input", "boolean_output", "missing_input"):
            with self.subTest(mutation=mutation):
                original = response()
                if mutation == "missing_cache":
                    original.usage.input_tokens_details = NS()
                elif mutation == "too_much_cache":
                    original.usage.input_tokens_details.cached_tokens = 101
                elif mutation == "too_much_reasoning":
                    original.usage.output_tokens_details.reasoning_tokens = 11
                elif mutation == "negative_input":
                    original.usage.input_tokens = -1
                elif mutation == "boolean_output":
                    original.usage.output_tokens = True
                else:
                    original.usage.input_tokens = None
                _, report = self.report(lambda: invoke(client(original)))
                self.assertIsNone(report["llm"]["estimated_cost_usd"])
                self.assertEqual(report["llm"]["cost_status"], "unavailable")

    def test_tools_and_unsupported_tiers_are_not_reported_as_complete_cost(self) -> None:
        _, report = self.report(lambda: invoke(client(response()), tools=[{"type": "web_search"}]))
        self.assertEqual(report["llm"]["cost_status"], "partial")
        for tier in ("priority", "flex"):
            _, report = self.report(lambda: invoke(client(response()), service_tier=tier))
            self.assertIsNone(report["llm"]["estimated_cost_usd"])
        original = response()
        original.usage.input_tokens_details.cache_write_tokens = 2
        _, report = self.report(lambda: invoke(client(original)))
        self.assertIsNone(report["llm"]["estimated_cost_usd"])

    def test_mixed_models_keep_known_part_and_do_not_claim_single_model(self) -> None:
        fake = client(response(), response())
        def run():
            invoke(fake)
            return create_response(fake, "bear_initial", model="gpt-other-test", input="private")
        _, report = self.report(run)
        self.assertIsNone(report["llm"]["model"])
        self.assertEqual(report["llm"]["cost_status"], "partial")
        self.assertEqual(report["llm"]["input_tokens"], 200)

    def test_stage_failure_and_privacy_allowlist(self) -> None:
        @measure_stage("bull_initial")
        def failing():
            raise ValueError("private-error-marker")
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                measure_analysis("Example", failing, Path(folder), pricing=PRICING)
            report = json.loads(next(Path(folder).glob("*.json")).read_text(encoding="utf-8"))
        self.assertEqual(report["stages"][0]["status"], "failed")
        def private_labels():
            with measure_stage("private-stage-marker"):
                return invoke(client(response()), "https://private.example/private-phase-marker")
        _, report = self.report(private_labels)
        self.assertEqual(report["stages"], [])
        self.assertEqual(report["llm"]["by_phase"][0]["phase"], "unclassified")
        self.assertNotIn("private", json.dumps(report))

    def test_stage_cap_is_explicit(self) -> None:
        def run():
            for _ in range(1002):
                with measure_stage("collect"):
                    pass
        _, report = self.report(run)
        self.assertEqual(len(report["stages"]), 1000)
        self.assertTrue(report["stages_truncated"])

    def test_cached_stage_has_no_api_charge_or_old_usage(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            checkpoint = AnalysisCheckpoint(root / "checkpoint.json", "unit-test")
            fake = client(response())
            @measure_stage("bull_initial")
            def paid():
                return invoke(fake).output_text
            for label in ("first", "cached"):
                measure_analysis(label, lambda: checkpoint.call("bull_initial-1", paid), root / "metrics", pricing=PRICING)
            records = {row["label"]: row for row in [json.loads(path.read_text(encoding="utf-8")) for path in (root / "metrics").glob("*.json")]}
        self.assertEqual(fake.responses.create.call_count, 1)
        self.assertEqual(records["first"]["llm"]["request_count"], 1)
        self.assertEqual(records["cached"]["llm"]["request_count"], 0)
        self.assertIsNone(records["cached"]["llm"]["estimated_cost_usd"])
        self.assertEqual(records["cached"]["stages"][0]["name"], "bull_initial")
        self.assertTrue(records["cached"]["stages"][0]["cached"])
        self.assertNotEqual(records["first"]["id"], records["cached"]["id"])

    def test_collector_and_writer_failure_preserve_result_and_original_error(self) -> None:
        with patch("tools.run_metrics._Measurements.response", side_effect=RuntimeError("measurement failed")):
            original = response()
            value, _ = self.report(lambda: invoke(client(original)))
            self.assertIs(value, original)
            error = ValueError("original")
            with self.assertRaises(ValueError) as caught:
                self.report(lambda: invoke(client(error)))
            self.assertIs(caught.exception, error)
        with patch("tools.run_metrics.Path.write_text", side_effect=OSError("disk")):
            with tempfile.TemporaryDirectory() as folder:
                self.assertEqual(measure_analysis("Example", lambda: 7, Path(folder), pricing=PRICING), 7)

    def test_parallel_contexts_are_separate_and_worker_copy_is_collected(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            def one(label):
                def run():
                    with ThreadPoolExecutor(max_workers=2) as children:
                        futures = [children.submit(copy_context().run, invoke, client(response()), phase) for phase in ("bull_initial", "bear_initial")]
                        return [future.result() for future in futures]
                return measure_analysis(label, run, root / label, pricing=PRICING)
            with ThreadPoolExecutor(max_workers=2) as executor:
                list(executor.map(one, ("one", "two")))
            records = [json.loads(next((root / label).glob("*.json")).read_text(encoding="utf-8")) for label in ("one", "two")]
        self.assertTrue(all(record["llm"]["request_count"] == 2 for record in records))
        self.assertNotEqual(records[0]["id"], records[1]["id"])

    def test_real_langgraph_parallel_nodes_keep_context(self) -> None:
        from langgraph.graph import StateGraph, START, END
        class State(TypedDict, total=False):
            bull: int
            bear: int
        fake = client(response(), response())
        @measure_stage("bull_initial")
        def bull(state: State) -> dict:
            invoke(fake)
            return {"bull": 1}
        @measure_stage("bear_initial")
        def bear(state: State) -> dict:
            invoke(fake, "bear_initial")
            return {"bear": 1}
        graph = StateGraph(State)
        graph.add_node("bull", bull)
        graph.add_node("bear", bear)
        for node in ("bull", "bear"):
            graph.add_edge(START, node)
            graph.add_edge(node, END)
        runnable = graph.compile()
        value, report = self.report(lambda: runnable.invoke({}))
        self.assertEqual(value, {"bull": 1, "bear": 1})
        self.assertEqual(report["llm"]["request_count"], 2)
        self.assertEqual({row["name"] for row in report["stages"]}, {"bull_initial", "bear_initial"})

    def test_pricing_metadata_is_bounded_and_invalid_override_has_no_fallback(self) -> None:
        _, report = self.report(lambda: invoke(client(response())), pricing={**PRICING, "source_url": "https://private.example/secret", "api_key": "private"})
        self.assertEqual(report["llm"]["pricing"], PRICING)
        self.assertNotIn("private.example", json.dumps(report))
        _, hidden = self.report(lambda: create_response(client(response()), "bull_initial", model="sk-private-model-marker", input="private"))
        self.assertIsNone(hidden["llm"]["model"])
        self.assertNotIn("private-model-marker", json.dumps(hidden))
        for invalid in ({}, {**PRICING, "source": []}, {**PRICING, "input_per_million": 10**400}, {**PRICING, "as_of": "bad"}, {**PRICING, "cached_input_per_million": 2}):
            _, report = self.report(lambda: invoke(client(response())), pricing=invalid)
            self.assertIsNone(report["llm"]["estimated_cost_usd"])
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            valid = root / "pricing.json"
            valid.write_text(json.dumps(PRICING), encoding="utf-8")
            with patch("tools.run_metrics._DEFAULT_PRICING", valid), patch.dict(os.environ, {"RESULTS_PRICING_FILE": str(root / "missing.json")}):
                _, report = self.report(lambda: invoke(client(response())), pricing=None)
                self.assertIsNone(report["llm"]["pricing"])
            malformed = root / "deep.json"
            malformed.write_text("[" * 2000 + "]" * 2000, encoding="utf-8")
            with patch.dict(os.environ, {"RESULTS_PRICING_FILE": str(malformed)}):
                _, report = self.report(lambda: invoke(client(response())), pricing=None)
                self.assertIsNone(report["llm"]["pricing"])
            with patch.dict(os.environ, {"RESULTS_PRICING_FILE": str(valid)}):
                _, report = self.report(lambda: invoke(client(response())), pricing=None)
                self.assertEqual(report["llm"]["pricing"], PRICING)


if __name__ == "__main__":
    unittest.main()
