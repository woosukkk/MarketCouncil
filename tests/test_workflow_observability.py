"""Exercise the production Bull/Bear executor without external services."""
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

os.environ.setdefault("OPENAI_API_KEY", "offline-test-key")
from app.debate_workflow import DebateWorkflow
from tools.run_metrics import create_response, measure_analysis, measure_stage


class WorkflowObservabilityTests(unittest.TestCase):
    def test_real_workflow_executor_preserves_measurement_context(self) -> None:
        workflow = object.__new__(DebateWorkflow)
        workflow.evidence_workflow = NS(run=lambda company: {
            "financial_data": {"ticker": "TEST"}, "shared_report_context": "synthetic",
            "bull_web_context": "", "bear_web_context": "", "source_data": {},
        })
        workflow.historical_collector = NS(collect=lambda *args: [])
        workflow.regime_workflow = NS(run=lambda *args: {})
        barrier = threading.Barrier(2)
        response = NS(status="completed", output_text="offline response", usage=NS(
            input_tokens=100, output_tokens=10,
            input_tokens_details=NS(cached_tokens=25),
            output_tokens_details=NS(reasoning_tokens=4)))
        client = NS(responses=NS(create=Mock(return_value=response)))
        def participant(phase):
            @measure_stage(phase)
            def analyze(**kwargs):
                barrier.wait(timeout=10)
                return create_response(client,phase,model="gpt-5-mini",input="private synthetic prompt").output_text
            return NS(analyze_with_context=analyze)
        workflow.bull_agent = participant("bull_initial")
        workflow.bear_agent = participant("bear_initial")
        workflow.sentiment_agent = NS(analyze=lambda *args, **kwargs: {})
        workflow.video_agent = NS(run_latest_short_topics=lambda *args: {})
        workflow.debate_agent = NS(run=lambda **kwargs: {"rounds": []})
        workflow.navigator_agent = NS(analyze=lambda debate: {})
        pricing = {"model":"gpt-5-mini","as_of":"2026-10-27","source":"manual","currency":"USD",
                   "input_per_million":0.25,"cached_input_per_million":0.025,"output_per_million":2}
        with tempfile.TemporaryDirectory() as folder, patch("app.debate_workflow.build_regime_context",return_value="synthetic"), patch("app.debate_workflow.EvidenceCatalog.build",return_value=[]), patch("app.debate_workflow.EvidenceCatalog.for_prompt",return_value=[]), patch("app.debate_workflow.EvidenceCatalog.resolve",side_effect=lambda debate,catalog:debate):
            result=measure_analysis("synthetic-offline",lambda:workflow.run("Example"),Path(folder),pricing=pricing)
            report=json.loads(next(Path(folder).glob("*.json")).read_text(encoding="utf-8"))
        self.assertEqual(result["rounds"],[])
        self.assertEqual(client.responses.create.call_count,2)
        self.assertEqual(report["llm"]["request_count"],2)
        self.assertEqual(report["llm"]["input_tokens"],200)
        self.assertEqual(report["llm"]["output_tokens"],20)
        self.assertEqual(report["llm"]["cached_input_tokens"],50)
        self.assertEqual(report["llm"]["reasoning_tokens"],8)
        self.assertEqual({row["phase"] for row in report["llm"]["by_phase"]},{"bull_initial","bear_initial"})
        self.assertEqual({row["name"] for row in report["stages"]},{"bull_initial","bear_initial"})
        self.assertNotIn("private",json.dumps(report))


if __name__ == "__main__":
    unittest.main()
