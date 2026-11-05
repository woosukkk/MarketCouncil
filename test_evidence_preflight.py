"""Offline primary-evidence preparation and the pre-model comparison boundary."""
import copy
import hashlib
import os
import sys
import tempfile
import unittest
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app import evidence_preflight as preflight
from app.comparison_workflow import ComparisonWorkflow
from tools.company_profiles import get_profile
from tools.evidence_readiness import evaluate_readiness

AS_OF=datetime.now(timezone(timedelta(hours=9))).date().isoformat()


def primary_manifest(company: str="Apple Inc.",ticker: str="AAPL",seed: str="original") -> dict:
    profile=get_profile(company,ticker)
    day=datetime.fromisoformat(AS_OF).date()
    documents=[]
    for kind,age in (("annual",300),("interim",45),("earnings",20)):
        body=(f"{profile['company_name']} {seed} {kind} operations and segment results. "*75
              +"Revenue was 100 USD and operating income was 20 USD for this reporting period. "*45
              +"Risk factors include liquidity, customer concentration and changes in demand. "*45)
        documents.append({"company_name":profile["company_name"],"ticker":ticker,
                          "document_id":ticker+"-"+kind,"document_type":kind,
                          "published_at":(day-timedelta(days=2)).isoformat(),
                          "report_date":(day-timedelta(days=age)).isoformat(),
                          "content":body,"content_hash":hashlib.sha256(body.encode()).hexdigest(),
                          "source_url":"https://"+profile["ir_sources"][0]["host"]+profile["ir_sources"][0]["path_prefixes"][0]+"synthetic-"+kind+".pdf",
                          "identity_verified":True,"body_extraction_status":"extracted","provider":"official_ir"})
    return {"company_name":profile["company_name"],"ticker":ticker,"documents":documents,"failures":[]}


def comparison() -> ComparisonWorkflow:
    workflow=ComparisonWorkflow.__new__(ComparisonWorkflow)
    workflow.graph=Mock()
    workflow.graph.invoke.return_value={}
    workflow.bull_tools=SimpleNamespace(retriever=SimpleNamespace(release_model=Mock()),
                                       get_company_financials=Mock(return_value={"ticker":"AAPL"}),
                                       search_regulatory_filings=Mock(return_value=[]))
    return workflow


class EvidencePreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        for name in ("_BASE","_BOUND"):
            if hasattr(preflight,name):
                patcher=patch.object(preflight,name,ContextVar("isolated-"+name,default=None))
                patcher.start();self.addCleanup(patcher.stop)

    def test_cached_metadata_and_claimed_ready_flags_never_replace_body_validation(self) -> None:
        manifest=primary_manifest()
        for document in manifest["documents"]:document.pop("content")
        manifest.update(status="ready",readiness_report={"status":"ready","counts":{"annual":99}})
        collector=Mock();collector.load.return_value=manifest
        with patch.object(preflight,"_BASE",ContextVar("test-base",default=None)),patch.object(preflight,"CompanyEvidenceCollector",return_value=collector):
            with self.assertRaises(preflight.EvidenceNotReady) as caught:
                preflight.require_company_ready("Apple","AAPL",refresh=False)
        self.assertEqual(caught.exception.report["status"],"insufficient")
        self.assertEqual(sum(caught.exception.report["counts"].values()),0)
        collector.collect.assert_not_called();collector.save.assert_not_called()

    def test_cached_body_is_rehashed_instead_of_trusting_stored_content_hash(self) -> None:
        manifest=primary_manifest()
        manifest["documents"][0]["content"]="changed local bytes "*120
        collector=Mock();collector.load.return_value=manifest
        with patch.object(preflight,"CompanyEvidenceCollector",return_value=collector):
            with self.assertRaises(preflight.EvidenceNotReady) as caught:
                preflight.require_company_ready("Apple","AAPL",refresh=False)
        self.assertIn("annual_missing",caught.exception.report["missing"])

    def test_refresh_reloads_saved_originals_and_failed_latest_earnings_fail_closed(self) -> None:
        manifest=primary_manifest()
        collector=Mock()
        collector.load.side_effect=[copy.deepcopy(manifest),copy.deepcopy(manifest)]
        collector.collect.return_value=copy.deepcopy(manifest)
        ir=Mock();ir.collect.return_value={"documents":[],"failures":[]}
        with patch.object(preflight,"CompanyEvidenceCollector",return_value=collector),patch.object(preflight,"_collection_settings") as settings,patch("tools.official_ir_collector.OfficialIRCollector",return_value=ir):
            with self.assertRaises(preflight.EvidenceNotReady) as caught:
                preflight.require_company_ready("Apple","AAPL",refresh=True)
        self.assertEqual(collector.load.call_count,2)
        collector.save.assert_called_once();settings.assert_called_once()
        self.assertIn("earnings_missing",caught.exception.report["missing"])

    def test_explicit_base_is_retained_when_the_working_directory_changes(self) -> None:
        manifest=primary_manifest();collector=Mock();collector.load.return_value=manifest
        original=Path.cwd()
        with tempfile.TemporaryDirectory() as folder,patch.object(preflight,"CompanyEvidenceCollector",return_value=collector) as factory:
            base=(Path(folder)/"corpus").resolve()
            _,report=preflight.require_company_ready("Apple","AAPL",refresh=False,base_dir=base)
            try:
                other=Path(folder)/"different-working-directory";other.mkdir();os.chdir(other)
                self.assertEqual(preflight.evidence_base(),base)
                _,again=preflight.require_company_ready("Apple","AAPL",refresh=False)
                self.assertEqual(again["corpus_hash"],report["corpus_hash"])
                self.assertEqual(factory.call_args.args[0],base)
            finally:os.chdir(original)

    def test_readiness_audit_cli_reuses_preflight_failure_flags_without_refresh_or_ai(self) -> None:
        from app import prepare_company_evidence as cli
        manifest=primary_manifest();manifest["latest_earnings_failed"]=True
        manifest["failures"]=[{"code":"download_failed","reason":"private provider detail"}]
        collector=Mock();collector.load.return_value=manifest
        with tempfile.TemporaryDirectory() as folder,patch.object(preflight,"CompanyEvidenceCollector",return_value=collector),patch.object(cli,"prepare_company",wraps=preflight.prepare_company) as prepare:
            result=cli.run(company="Apple",ticker="AAPL",refresh=False,base_dir=Path(folder))
        self.assertIs(prepare.call_args.kwargs["refresh"],False)
        self.assertEqual(result["scope"],"evidence_readiness")
        self.assertEqual(result["settings"]["case_count"],1)
        self.assertEqual(result["companies"][0]["status"],"insufficient")
        self.assertIn("earnings_missing",result["companies"][0]["missing"])
        self.assertNotIn("private provider detail",repr(result))
        collector.collect.assert_not_called()

    def test_primary_chunks_are_bounded_literal_excerpts_with_approved_source_identity(self) -> None:
        manifest=primary_manifest();report=evaluate_readiness(manifest,AS_OF)
        chunks=preflight.primary_chunks(manifest,report)
        self.assertEqual(report["status"],"ready");self.assertTrue(chunks);self.assertLessEqual(len(chunks),9)
        sources={doc["source_url"]:doc for doc in manifest["documents"]}
        for chunk in chunks:
            original=sources[chunk["source"]]
            self.assertIn(chunk["text"],original["content"])
            self.assertLessEqual(len(chunk["text"]),2000)
            self.assertEqual(chunk["metadata"]["company"],manifest["company_name"])
            self.assertEqual(chunk["metadata"]["ticker"],manifest["ticker"])
            self.assertEqual(chunk["metadata"]["content_hash"],original["content_hash"])

    def test_other_company_with_same_body_hash_or_changed_body_cannot_enter_primary_chunks(self) -> None:
        manifest=primary_manifest();report=evaluate_readiness(manifest,AS_OF)
        expected=preflight.primary_chunks(manifest,report)
        foreign=copy.deepcopy(manifest["documents"][0])
        foreign.update(company_name="Microsoft Corporation",ticker="MSFT",document_id="foreign-annual",
                       source_url="https://www.microsoft.com/en-us/investor/foreign.pdf",published_at=AS_OF)
        polluted=copy.deepcopy(manifest);polluted["documents"].insert(0,foreign)
        self.assertEqual(preflight.primary_chunks(polluted,report),expected)
        tampered=copy.deepcopy(manifest)
        tampered["documents"][0]["content"]="UNAPPROVED BODY "*150
        chunks=preflight.primary_chunks(tampered,report)
        self.assertFalse(any("UNAPPROVED" in chunk["text"] for chunk in chunks))
        self.assertFalse(any(chunk["metadata"]["content_hash"]==report["documents"][0]["content_hash"] for chunk in chunks))

    def test_source_cli_saves_the_verified_financial_readiness_report_at_top_level(self) -> None:
        from app import debate_main
        manifest=primary_manifest();report=evaluate_readiness(manifest,AS_OF)
        debate={"company_name":"Apple Inc.","financial_data":{"ticker":"AAPL","readiness_report":report},"rounds":[]}
        events=[]
        def prepare(company: str,ticker: str,**kwargs: object) -> tuple:
            events.append("gate");return manifest,report
        def services() -> None:
            self.assertEqual(os.environ["MARKETCOUNCIL_COMPANY"],"Apple Inc.")
            self.assertEqual(os.environ["MARKETCOUNCIL_TICKER"],"AAPL")
            events.append("services")
        with patch.dict(os.environ,{"RESULTS_AUTO_UPLOAD":"false","MARKETCOUNCIL_COMPANY":"삼성전자","MARKETCOUNCIL_TICKER":"005930.KS"}),patch.object(sys,"argv",["debate_main"]),patch("builtins.input",return_value="Apple"),patch("builtins.print"),patch("tools.company_lookup.resolve_ticker",return_value="AAPL") as resolve,patch.object(preflight,"require_company_ready",side_effect=prepare) as gate,patch.object(debate_main,"ensure_local_services",side_effect=services),patch.object(debate_main,"DebateWorkflow") as workflow,patch.object(debate_main,"AnalysisDebateStore") as store,patch.object(debate_main,"DebateTranscriptRenderer"),patch.object(debate_main,"RegimeStore"),patch.object(debate_main,"load_dotenv"):
            workflow.return_value.run.side_effect=lambda company:events.append("analysis") or debate
            self.assertEqual(debate_main.main(),0)
            resolve.assert_called_once();gate.assert_called_once()
            self.assertEqual(gate.call_args.args,("Apple","AAPL"))
            self.assertEqual(events,["gate","services","analysis"])
            self.assertEqual(store.return_value.save.call_args.args[0],"Apple Inc.")
            saved=store.return_value.save.call_args.args[1]
            self.assertIs(saved["readiness_report"],report)
            self.assertIs(saved["financial_data"]["readiness_report"],report)

    def test_source_cli_insufficient_body_stops_before_docker_model_or_result_save(self) -> None:
        from app import debate_main
        manifest=primary_manifest();manifest["documents"]=[]
        report=evaluate_readiness(manifest,AS_OF)
        with patch.dict(os.environ,{"RESULTS_AUTO_UPLOAD":"false"}),patch.object(sys,"argv",["debate_main"]),patch("builtins.input",return_value="Apple"),patch("builtins.print"),patch("tools.company_lookup.resolve_ticker",return_value="AAPL"),patch.object(preflight,"require_company_ready",side_effect=preflight.EvidenceNotReady(report)) as gate,patch.object(debate_main,"ensure_local_services") as services,patch.object(debate_main,"DebateWorkflow") as workflow,patch.object(debate_main,"AnalysisDebateStore") as store:
            self.assertEqual(debate_main.main(),1)
            gate.assert_called_once();services.assert_not_called();workflow.assert_not_called();store.assert_not_called()

    def test_source_cli_check_mode_only_checks_services_without_company_or_paid_gate(self) -> None:
        from app import debate_main
        with patch.object(sys,"argv",["debate_main","--check"]),patch("builtins.input") as company,patch("builtins.print"),patch("tools.company_lookup.resolve_ticker") as resolve,patch.object(preflight,"require_company_ready") as gate,patch.object(debate_main,"ensure_local_services") as services,patch.object(debate_main,"DebateWorkflow") as workflow:
            self.assertEqual(debate_main.main(),0)
            services.assert_called_once();company.assert_not_called();resolve.assert_not_called();gate.assert_not_called();workflow.assert_not_called()

    def test_comparison_insufficient_gate_stops_before_graph_or_financial_or_source_calls(self) -> None:
        workflow=comparison();manifest=primary_manifest();manifest["documents"]=[]
        report=evaluate_readiness(manifest,AS_OF)
        with patch.object(preflight,"require_company_ready",side_effect=preflight.EvidenceNotReady(report)),patch("tools.company_lookup.resolve_ticker",return_value="AAPL"):
            with self.assertRaises(preflight.EvidenceNotReady):workflow.run("Apple Inc.")
        workflow.graph.invoke.assert_not_called();workflow.bull_tools.get_company_financials.assert_not_called()
        workflow.bull_tools.search_regulatory_filings.assert_not_called();workflow.bull_tools.retriever.release_model.assert_called_once()

    def test_comparison_passes_primary_chunks_into_filings_and_preserves_financial_report(self) -> None:
        workflow=comparison();manifest=primary_manifest();report=evaluate_readiness(manifest,AS_OF)
        workflow.graph.invoke.side_effect=lambda state:state
        with patch.object(preflight,"require_company_ready",return_value=(manifest,report)) as gate,patch("tools.company_lookup.resolve_ticker",return_value="AAPL"):
            state=workflow.run("Apple Inc.")
        self.assertIs(state["readiness_report"],report);self.assertTrue(state["primary_chunks"])
        self.assertIs(gate.call_args.kwargs["refresh"],False)
        workflow.bull_tools.search_regulatory_filings.return_value=state["primary_chunks"][:1]
        filings=workflow.retrieve_regulatory_filings(state)["filing_chunks"]
        self.assertEqual(filings,state["primary_chunks"])
        finances=workflow.collect_financial_data(state)["financial_data"]
        self.assertIs(finances["readiness_report"],report)


if __name__=="__main__":unittest.main()
