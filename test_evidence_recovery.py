"""Offline recovery rechecks live primary bodies before consulting completed stages."""
import json
import sys
import tempfile
import unittest
from contextlib import ExitStack
from contextvars import ContextVar
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app import evidence_preflight as preflight
from app.comparison_workflow import ComparisonWorkflow
from app.recoverable_debate_workflow import RecoverableDebateWorkflow
from desktop.preferences import VERSION
from tools.evidence_readiness import evaluate_readiness
from test_evidence_preflight import AS_OF, primary_manifest, comparison


class EvidenceRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.folder=Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        for name in ("_BASE","_BOUND"):
            if hasattr(preflight,name):self.stack.enter_context(patch.object(preflight,name,ContextVar("isolated-"+name,default=None)))
        (self.folder/"release-build.json").write_text(json.dumps({"version":VERSION,"source_commit":"a"*40}),encoding="utf-8")
        self.stack.enter_context(patch.object(sys,"frozen",True,create=True))
        self.stack.enter_context(patch.object(sys,"_MEIPASS",str(self.folder),create=True))
        self.calls=[]
        self.real_comparison=None
        def initialize(owner: object) -> None:
            def collect(company: str) -> dict:
                self.calls.append(("collect",company))
                return {"company":company,"collected":"synthetic complete stage"}
            owner.evidence_workflow=self.real_comparison or SimpleNamespace(run=Mock(side_effect=collect))
            owner.historical_collector=SimpleNamespace(collect=Mock(return_value=[]))
            owner.regime_workflow=SimpleNamespace(run=Mock(return_value={}))
            owner.bull_agent=SimpleNamespace(analyze_with_context=Mock(return_value="bull"))
            owner.bear_agent=SimpleNamespace(analyze_with_context=Mock(return_value="bear"))
            owner.sentiment_agent=SimpleNamespace(analyze=Mock(return_value={}))
            owner.video_agent=SimpleNamespace(run_latest_short_topics=Mock(return_value={}))
            owner.navigator_agent=SimpleNamespace(analyze=Mock(return_value={}))
            owner.debate_agent=SimpleNamespace(**{name:Mock(return_value={}) for name in ("create_agenda","bull_turn","bear_turn","moderator_review","summarize")},_build_graph=Mock(return_value="synthetic graph"))
        def execute(owner: object,company: str) -> dict:
            return {"company_name":company,"context":owner.evidence_workflow.run(company),
                    "turn":owner.debate_agent.bull_turn({"current_round":1})}
        self.stack.enter_context(patch("app.recoverable_debate_workflow.DebateWorkflow.__init__",initialize))
        self.stack.enter_context(patch("app.recoverable_debate_workflow.DebateWorkflow.run",execute))

    def workflow(self,company: str,ticker: str,report: dict) -> RecoverableDebateWorkflow:
        return RecoverableDebateWorkflow(self.folder/"checkpoint.json",company,AS_OF,ticker=ticker,corpus_hash=report["corpus_hash"])

    def test_same_verified_body_and_ticker_reuse_completed_stages_but_recheck_gate_each_run(self) -> None:
        manifest=primary_manifest();report=evaluate_readiness(manifest,AS_OF)
        with patch.object(preflight,"require_company_ready",return_value=(manifest,report)) as gate:
            first=self.workflow("Apple Inc.","AAPL",report)
            result=first.run("Apple Inc.")
            self.assertEqual(first.run("Apple Inc."),result)
            second=self.workflow("Apple Inc.","AAPL",report)
            self.assertEqual(second.run("Apple Inc."),result)
        self.assertEqual(self.calls,[("collect","Apple Inc.")])
        self.assertEqual(gate.call_count,3)
        self.assertTrue(all(call.kwargs["refresh"] is False for call in gate.call_args_list))
        self.assertEqual(result["readiness_report"],report)
        self.assertEqual(len(list(self.folder.glob("checkpoint-*.json"))),1)

    def test_different_corpus_or_ticker_uses_separate_cache_and_leaves_original_file(self) -> None:
        original=self.folder/"checkpoint.json";legacy=b"old source/version checkpoint retained verbatim";original.write_bytes(legacy)
        cases=[("Apple Inc.","AAPL","original"),("Apple Inc.","AAPL","changed"),("Microsoft Corporation","MSFT","original")]
        for company,ticker,seed in cases:
            manifest=primary_manifest(company,ticker,seed);report=evaluate_readiness(manifest,AS_OF)
            with patch.object(preflight,"require_company_ready",return_value=(manifest,report)):
                self.workflow(company,ticker,report).run(company)
        self.assertEqual(len(self.calls),len(cases))
        self.assertEqual(original.read_bytes(),legacy)
        paths=list(self.folder.glob("checkpoint-*.json"));self.assertEqual(len(paths),len(cases))
        scopes=[json.loads(path.read_text(encoding="utf-8"))["scope"] for path in paths]
        self.assertEqual(len(set(scopes)),len(cases))
        self.assertTrue(any("AAPL" in scope for scope in scopes));self.assertTrue(any("MSFT" in scope for scope in scopes))

    def test_newly_insufficient_or_metadata_only_body_cannot_replay_cached_collect(self) -> None:
        manifest=primary_manifest();report=evaluate_readiness(manifest,AS_OF)
        workflow=self.workflow("Apple Inc.","AAPL",report)
        with patch.object(preflight,"require_company_ready",return_value=(manifest,report)):
            workflow.run("Apple Inc.")
        metadata=primary_manifest()
        for document in metadata["documents"]:document.pop("content")
        metadata["readiness_report"]=report
        insufficient=evaluate_readiness(metadata,AS_OF)
        self.assertEqual(insufficient["status"],"insufficient")
        with patch.object(preflight,"require_company_ready",side_effect=preflight.EvidenceNotReady(insufficient)) as gate:
            with self.assertRaises(preflight.EvidenceNotReady):workflow.run("Apple Inc.")
        gate.assert_called_once();self.assertEqual(self.calls,[("collect","Apple Inc.")])

    def test_expected_corpus_or_company_mismatch_stops_before_paid_stage_or_cache_use(self) -> None:
        original=primary_manifest();original_report=evaluate_readiness(original,AS_OF)
        changed=primary_manifest(seed="changed");changed_report=evaluate_readiness(changed,AS_OF)
        workflow=self.workflow("Apple Inc.","AAPL",original_report)
        with patch.object(preflight,"require_company_ready",return_value=(changed,changed_report)) as gate:
            with self.assertRaisesRegex(ValueError,"근거 묶음"):workflow.run("Apple Inc.")
            gate.reset_mock()
            with self.assertRaisesRegex(ValueError,"기업"):workflow.run("Microsoft Corporation")
            gate.assert_not_called()
        self.assertEqual(self.calls,[])
        self.assertFalse(list(self.folder.glob("checkpoint-*.json")))

    def test_body_changed_between_resume_gate_and_graph_gate_cannot_enter_graph(self) -> None:
        initial=primary_manifest();initial_report=evaluate_readiness(initial,AS_OF)
        changed=primary_manifest(seed="changed");changed_report=evaluate_readiness(changed,AS_OF)
        self.real_comparison=comparison()
        workflow=self.workflow("Apple Inc.","AAPL",initial_report)
        with patch.object(preflight,"prepare_company",side_effect=[(initial,initial_report),(changed,changed_report)]),patch("tools.company_lookup.resolve_ticker",return_value="AAPL"):
            with self.assertRaises(ValueError):workflow.run("Apple Inc.")
        self.real_comparison.graph.invoke.assert_not_called()
        self.real_comparison.bull_tools.get_company_financials.assert_not_called()


if __name__=="__main__":unittest.main()
