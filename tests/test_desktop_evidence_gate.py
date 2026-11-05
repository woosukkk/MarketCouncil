"""Offline Desktop and daily publication evidence gates; no model or provider calls."""
import copy
import hashlib
import json
import os
import queue
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from desktop import cloud, daily_official as daily
from desktop.main import Desktop
from tools.company_profiles import PROFILES, get_profile
from tools.evidence_readiness import evaluate_readiness

DAY="2026-11-03"
SESSION={"user":{"id":"synthetic-owner"},"access_token":"synthetic-token"}


def ready_report(company: str="삼성전자", ticker: str="005930.KS", day: str | None=None, seed: str="original") -> dict:
    day=day or cloud.official_day()
    cutoff=date.fromisoformat(day)
    profile=get_profile(company,ticker)
    documents=[]
    for kind, age in (("annual",300),("interim",45),("earnings",20)):
        body=(f"Synthetic {kind} {seed}: revenue 100 USD, operating income 20 USD. "*30)
        documents.append({"company_name":profile["company_name"],"ticker":ticker,
                          "document_id":ticker+"-"+kind,"document_type":kind,
                          "published_at":(cutoff-timedelta(days=2)).isoformat(),
                          "report_date":(cutoff-timedelta(days=age)).isoformat(),
                          "content":body,"content_hash":hashlib.sha256(body.encode()).hexdigest(),
                          "source_url":"https://"+profile["ir_sources"][0]["host"]+profile["ir_sources"][0]["path_prefixes"][0]+"synthetic-"+kind+".pdf",
                          "identity_verified":True,"provider":"official_ir"})
    return evaluate_readiness({"company_name":profile["company_name"],"ticker":ticker,"documents":documents},day)


def ready_result(company: str="삼성전자", ticker: str="005930.KS", day: str | None=None, seed: str="original") -> dict:
    profile=get_profile(company,ticker)
    return {"company_name":profile["company_name"],"financial_data":{"ticker":ticker},"rounds":[],
            "readiness_report":ready_report(company,ticker,day,seed)}


def preflight() -> SimpleNamespace:
    return SimpleNamespace(prepare_company=Mock(),require_company_ready=Mock())


class OfficialEvidenceGateTests(unittest.TestCase):
    def test_all_six_ready_profiles_can_publish_without_replacing_existing_selection(self) -> None:
        for profile in PROFILES:
            data=ready_result(profile["company_name"],profile["ticker"],DAY)
            self.assertEqual(data["readiness_report"]["status"],"ready")
            with self.subTest(company=profile["company_name"]),patch.object(cloud,"official_day",return_value=DAY),patch.object(cloud,"request",side_effect=[True,[],cloud.CloudAPIError(400),DAY]) as api,patch.object(cloud,"upload_result") as upload:
                self.assertEqual(cloud.publish_official(data,SESSION),DAY)
                self.assertIs(api.call_args.args[1]["replace_existing"],False)
                upload.assert_called_once()

    def test_missing_insufficient_tampered_wrong_company_and_old_reports_never_call_http(self) -> None:
        cases=[]
        missing=ready_result(day=DAY);missing.pop("readiness_report");cases.append(missing)
        insufficient=ready_result(day=DAY)
        insufficient["readiness_report"]=evaluate_readiness({"company_name":"삼성전자","ticker":"005930.KS","documents":[]},DAY)
        cases.append(insufficient)
        tampered=ready_result(day=DAY);tampered["readiness_report"]["counts"]["annual"]=99;cases.append(tampered)
        wrong=ready_result(day=DAY);wrong["financial_data"]["ticker"]="AAPL";cases.append(wrong)
        cases.append(ready_result(day="2026-11-02"))
        for data in cases:
            with self.subTest(company=data["company_name"],report=data.get("readiness_report",{}).get("status")),patch.object(cloud,"official_day",return_value=DAY),patch.object(cloud,"request") as api,patch.object(cloud,"upload_result") as upload:
                with self.assertRaises(ValueError):cloud.publish_official(data,SESSION)
                api.assert_not_called();upload.assert_not_called()

    def test_official_history_reads_public_readiness_metadata_for_event_replay_checks(self) -> None:
        report=ready_report(day=DAY)
        rows=[{"publication_date":DAY,"discussions":{"company_name":"삼성전자","ticker":"005930.KS","readiness_report":report}}]
        with patch.object(cloud,"request",return_value=rows) as api:
            result=cloud.official_history(SESSION)
        self.assertEqual(result[0]["corpus_hash"],report["corpus_hash"])
        self.assertEqual(result[0]["documents"],report["documents"])
        self.assertIn("readiness_report:payload->readiness_report",api.call_args.args[0])
        self.assertIn("discussions.visibility=eq.public",api.call_args.args[0])
        self.assertEqual(api.call_args.kwargs["method"],"GET")


class DailyEvidenceGateTests(unittest.TestCase):
    def test_all_insufficient_candidates_block_before_an_attempt_or_publication(self) -> None:
        module=preflight()
        module.prepare_company.side_effect=lambda company,ticker,**kwargs: ({},evaluate_readiness({"company_name":company,"ticker":ticker,"documents":[]},DAY))
        state={};analyze=Mock();publish=Mock();persist=Mock()
        with patch.dict(sys.modules,{"app.evidence_preflight":module}),patch.object(cloud,"official_history",return_value=[]):
            with self.assertRaisesRegex(ValueError,"충분한 기업"):
                daily.run_once(state,DAY,lambda:daily.prepare_target({"official_mode":"eligible"},state,DAY,SESSION),analyze,publish,persist)
        self.assertEqual(module.prepare_company.call_count,len(PROFILES))
        analyze.assert_not_called();publish.assert_not_called();persist.assert_not_called()
        self.assertEqual(state,{})

    def test_eligible_mode_selects_only_ready_company_and_legacy_defaults_to_samsung(self) -> None:
        module=preflight()
        def collect(company: str,ticker: str,**kwargs: object) -> tuple:
            report=ready_report(company,ticker,DAY) if ticker=="AAPL" else evaluate_readiness({"company_name":company,"ticker":ticker,"documents":[]},DAY)
            return {},report
        module.prepare_company.side_effect=collect
        module.require_company_ready.return_value=({},ready_report(day=DAY))
        with patch.dict(sys.modules,{"app.evidence_preflight":module}),patch.object(cloud,"official_history",return_value=[]) as history:
            selected=daily.prepare_target({"official_mode":"eligible"},{},DAY,SESSION)
            self.assertEqual((selected["company_name"],selected["ticker"]),("Apple Inc.","AAPL"))
            self.assertEqual(module.prepare_company.call_count,len(PROFILES))
            self.assertEqual(daily.prepare_target({}, {},DAY,SESSION)["ticker"],"005930.KS")
            self.assertEqual(history.call_count,1)

    def test_failed_day_keeps_company_corpus_and_two_attempt_cap_when_mode_changes(self) -> None:
        report=ready_report("Apple","AAPL",DAY)
        target={"company_name":"Apple Inc.","ticker":"AAPL","readiness_report":report}
        state={};paid=Mock(side_effect=RuntimeError("synthetic analysis failure"))
        with self.assertRaises(RuntimeError):daily.run_once(state,DAY,Mock(),paid,Mock(),Mock(),resume=True,target=target)
        self.assertEqual(state["target"],target)
        module=preflight();module.require_company_ready.return_value=({},report)
        with patch.dict(sys.modules,{"app.evidence_preflight":module}),patch.object(cloud,"official_history") as history:
            resumed=daily.prepare_target({"official_mode":"samsung"},state,DAY,SESSION)
            self.assertEqual(resumed["ticker"],"AAPL")
            self.assertIs(module.require_company_ready.call_args.kwargs["refresh"],False)
            with self.assertRaises(RuntimeError):daily.run_once(state,DAY,Mock(),paid,Mock(),Mock(),resume=True,target=resumed)
            self.assertEqual(state["analysis_attempts"],2)
            self.assertEqual(daily.run_once(state,DAY,Mock(),paid,Mock(),Mock(),resume=True,target=resumed),"skipped")
            self.assertEqual(paid.call_count,2)
            module.prepare_company.assert_not_called();history.assert_not_called()
        self.assertEqual(state["target"]["readiness_report"]["corpus_hash"],report["corpus_hash"])

    def test_changed_corpus_blocks_resume_before_another_paid_attempt(self) -> None:
        original=ready_report("Apple","AAPL",DAY)
        target={"company_name":"Apple Inc.","ticker":"AAPL","readiness_report":original}
        state={"day":DAY,"status":"analysis_failed","analysis_attempts":1,"target":target}
        before=copy.deepcopy(state)
        module=preflight();module.require_company_ready.return_value=({},ready_report("Apple","AAPL",DAY,"changed"))
        analyze=Mock();persist=Mock()
        with patch.dict(sys.modules,{"app.evidence_preflight":module}):
            with self.assertRaisesRegex(ValueError,"근거가 변경"):
                daily.run_once(state,DAY,lambda:daily.prepare_target({"official_mode":"eligible"},state,DAY,SESSION),analyze,Mock(),persist,resume=True,target={})
        analyze.assert_not_called();persist.assert_not_called();self.assertEqual(state,before)

    def test_saved_result_retry_never_reselects_or_recollects_and_keeps_original_path(self) -> None:
        module=preflight();analyze=Mock();publish=Mock(side_effect=[RuntimeError("synthetic network"),None])
        data=ready_result("Apple","AAPL",DAY)
        target={"company_name":data["company_name"],"ticker":"AAPL","readiness_report":data["readiness_report"]}
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"saved.json";path.write_text(json.dumps(data),encoding="utf-8")
            state={"day":DAY,"status":"pending_upload","analysis_attempts":1,"result_path":str(path),"target":target}
            with patch.dict(sys.modules,{"app.evidence_preflight":module}),patch.object(cloud,"official_history") as history:
                for should_fail in (True,False):
                    prepare=lambda:daily.prepare_target({"official_mode":"samsung"},state,DAY,SESSION)
                    if should_fail:
                        with self.assertRaises(RuntimeError):daily.run_once(state,DAY,prepare,analyze,publish,Mock(),resume=True,target=target)
                    else:self.assertEqual(daily.run_once(state,DAY,prepare,analyze,publish,Mock(),resume=True,target=target),"completed")
                analyze.assert_not_called();module.prepare_company.assert_not_called();module.require_company_ready.assert_not_called();history.assert_not_called()
                self.assertEqual(publish.call_args_list[0].args,publish.call_args_list[1].args)
                self.assertEqual(state["result_path"],str(path));self.assertEqual(state["analysis_attempts"],1)
                self.assertEqual(state["target"],target)

    def test_saved_result_with_changed_corpus_cannot_replace_pinned_result(self) -> None:
        module=preflight()
        original=ready_result("Apple","AAPL",DAY)
        changed=ready_result("Apple","AAPL",DAY,"changed")
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"saved.json";path.write_text(json.dumps(changed),encoding="utf-8")
            state={"day":DAY,"status":"pending_upload","analysis_attempts":1,"result_path":str(path),
                   "target":{"company_name":"Apple Inc.","ticker":"AAPL","readiness_report":original["readiness_report"]}}
            with patch.dict(sys.modules,{"app.evidence_preflight":module}),patch.object(cloud,"request") as api:
                with self.assertRaisesRegex(ValueError,"근거가 다릅니다"):
                    daily.prepare_target({"official_mode":"eligible"},state,DAY,SESSION)
                api.assert_not_called();module.prepare_company.assert_not_called();module.require_company_ready.assert_not_called()

    def test_remote_today_selection_skips_gate_and_services_without_paid_work(self) -> None:
        session={**SESSION,"refresh_token":"synthetic-rotated"}
        with tempfile.TemporaryDirectory() as folder,patch.object(daily,"DATA",Path(folder)),patch.object(daily,"today",return_value=DAY),patch.object(daily,"credentials",return_value={"refresh_token":"synthetic-original"}),patch.object(daily,"save_credentials"),patch.object(daily,"source_version",return_value="synthetic"),patch.object(daily,"prepare_target") as gate,patch.object(cloud,"request",side_effect=[session,True,[{"discussion_id":"already-published"}]]) as api,patch.object(daily,"prepare_runtime") as services,patch.object(daily,"notify") as notification:
            self.assertEqual(daily.run(),0)
            self.assertEqual(api.call_count,3)
            gate.assert_not_called();services.assert_not_called();notification.assert_not_called()
            self.assertEqual(json.loads((Path(folder)/"state.json").read_text(encoding="utf-8")),{"day":DAY,"status":"completed"})

    def test_daily_evidence_prepare_receives_explicit_keys_and_preserves_absent_sec_setting(self) -> None:
        for setting in (None,"","MarketCouncil explicit-contact@example.test"):
            config={"refresh_token":"synthetic-original","dart_key":"synthetic-dart"}
            if setting is not None:config["sec_user_agent"]=setting
            session={**SESSION,"refresh_token":"synthetic-rotated"}
            expected=setting or "MarketCouncil inherited-contact@example.test"
            def gate(*args: object) -> dict:
                self.assertEqual(os.environ["DART_API_KEY"],"synthetic-dart")
                self.assertEqual(os.environ["SEC_USER_AGENT"],expected)
                raise ValueError("Synthetic insufficient evidence")
            with self.subTest(setting=setting),tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{"SEC_USER_AGENT":"MarketCouncil inherited-contact@example.test"}),patch.object(daily,"DATA",Path(folder)),patch.object(daily,"today",return_value=DAY),patch.object(daily,"credentials",return_value=config),patch.object(daily,"save_credentials"),patch.object(daily,"source_version",return_value="synthetic"),patch.object(daily,"prepare_target",side_effect=gate) as preflight,patch.object(cloud,"request",side_effect=[session,True,[],cloud.CloudAPIError(400)]),patch.object(daily,"prepare_runtime") as services,patch.object(daily,"save_failure") as failure,patch.object(daily,"notify"):
                self.assertEqual(daily.run(),1)
                preflight.assert_called_once();services.assert_not_called()
                self.assertEqual(failure.call_args.args[0],"evidence")
                self.assertFalse((Path(folder)/"state.json").exists())

    def test_today_completed_state_skips_gate_services_and_account_http(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/"state.json").write_text(json.dumps({"day":DAY,"status":"completed"}),encoding="utf-8")
            with patch.object(daily,"DATA",root),patch.object(daily,"today",return_value=DAY),patch.object(daily,"credentials",return_value={}),patch.object(daily,"source_version",return_value="synthetic"),patch.object(daily,"prepare_target") as gate,patch.object(cloud,"request") as api,patch.object(daily,"prepare_runtime") as services,patch.object(daily,"notify"):
                self.assertEqual(daily.run(),0)
            gate.assert_not_called();api.assert_not_called();services.assert_not_called()


class DesktopEvidenceGateTests(unittest.TestCase):
    def desktop(self) -> Desktop:
        owner=Desktop.__new__(Desktop)
        for name in ("company","key","dart","search","company_choice"):
            setattr(owner,name,Mock())
        owner.company.get.return_value="Apple";owner.key.get.return_value="synthetic-offline-key"
        owner.dart.get.return_value="";owner.search.get.return_value="http://127.0.0.1:8080"
        owner.company_choice.current.return_value=0
        owner.company_candidates=[{"name":"Apple Inc.","ticker":"AAPL"}];owner.matched_name="Apple"
        owner.busy=False;owner.loaded_settings=None;owner.messages=queue.Queue();owner.session=SESSION
        owner.task=Mock(side_effect=lambda work,*args:work())
        return owner

    def test_insufficient_evidence_stops_before_services_or_models(self) -> None:
        owner=self.desktop();module=preflight();module.require_company_ready.side_effect=ValueError("자료 부족")
        workflow=Mock();services=Mock()
        with patch.dict(os.environ,{}),patch.dict(sys.modules,{"app.evidence_preflight":module,"app.debate_workflow":workflow,"app.local_services":services}),patch("desktop.main.messagebox.askyesno",return_value=True):
            with self.assertRaisesRegex(ValueError,"자료 부족"):owner.run()
        workflow.DebateWorkflow.assert_not_called();services.ensure_local_services.assert_not_called()
        self.assertEqual(module.require_company_ready.call_args.args,("Apple Inc.","AAPL"))

    def test_desktop_supplies_explicit_provider_settings_before_free_and_analysis_gates(self) -> None:
        owner=self.desktop();module=preflight()
        owner.dart.get.return_value="synthetic-dart"
        owner.sec_user_agent=SimpleNamespace(get=lambda:"MarketCouncil explicit-contact@example.test")
        def gate(company: str,ticker: str,**kwargs: object) -> tuple:
            self.assertEqual(os.environ["DART_API_KEY"],"synthetic-dart")
            self.assertEqual(os.environ["SEC_USER_AGENT"],"MarketCouncil explicit-contact@example.test")
            raise ValueError("Synthetic insufficient evidence")
        module.require_company_ready.side_effect=gate
        module.prepare_company.return_value=({},ready_report("Apple","AAPL",DAY))
        with patch.dict(os.environ,{}),patch.dict(sys.modules,{"app.evidence_preflight":module}),patch("desktop.main.messagebox.askyesno",return_value=True):
            with self.assertRaisesRegex(ValueError,"Synthetic insufficient"):owner.run()
            module.prepare_company.side_effect=gate
            with self.assertRaisesRegex(ValueError,"Synthetic insufficient"):owner.prepare_evidence()
        module.require_company_ready.assert_called_once();module.prepare_company.assert_called_once()

    def test_legacy_desktop_owner_keeps_explicit_environment_contact(self) -> None:
        owner=self.desktop();module=preflight()
        def gate(*args: object,**kwargs: object) -> tuple:
            self.assertEqual(os.environ["SEC_USER_AGENT"],"MarketCouncil inherited-contact@example.test")
            raise ValueError("Synthetic insufficient evidence")
        module.require_company_ready.side_effect=gate
        with patch.dict(os.environ,{"SEC_USER_AGENT":"MarketCouncil inherited-contact@example.test"}),patch.dict(sys.modules,{"app.evidence_preflight":module}),patch("desktop.main.messagebox.askyesno",return_value=True):
            with self.assertRaisesRegex(ValueError,"Synthetic insufficient"):owner.run()

    def test_today_already_published_stops_before_preflight_and_paid_work(self) -> None:
        owner=self.desktop();module=preflight()
        with patch.dict(os.environ,{}),patch.dict(sys.modules,{"app.evidence_preflight":module}),patch.object(cloud,"prepare_official",side_effect=ValueError("오늘 공식 토론이 이미 게시")),patch("desktop.main.messagebox.askyesno",return_value=True):
            with self.assertRaisesRegex(ValueError,"이미 게시"):owner.run(official=True)
        module.require_company_ready.assert_not_called()


if __name__=="__main__":unittest.main()
