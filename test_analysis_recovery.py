import os
os.environ.setdefault("OPENAI_API_KEY","test-key")
import json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock,patch
from tools.structured_response import structured_response,ResponseIncomplete
from tools.analysis_checkpoint import AnalysisCheckpoint

SCHEMA={"type":"object","properties":{},"additionalProperties":False}
def response(status="completed",reason=None,text='{}'):
    return NS(status=status,incomplete_details=NS(reason=reason),output_text=text,usage=NS(input_tokens=10,output_tokens=20,output_tokens_details=NS(reasoning_tokens=1)))
class RemoteError(Exception):
    def __init__(self,status,code=None):self.status_code=status;self.code=code
class RecoveryTests(unittest.TestCase):
    def client(self,items):return NS(responses=NS(create=Mock(side_effect=items)))
    def test_limit_retry_and_incomplete_reason(self):
        client=self.client([response("incomplete","max_output_tokens"),response()])
        self.assertEqual(structured_response(client,'i','input','phase',SCHEMA),{})
        self.assertEqual([x.kwargs['max_output_tokens'] for x in client.responses.create.call_args_list],[4000,8000])
        client=self.client([response("incomplete","content_filter")])
        with self.assertRaises(ResponseIncomplete) as error:structured_response(client,'i','input','phase',SCHEMA)
        self.assertEqual(error.exception.incomplete_reason,'content_filter');self.assertEqual(client.responses.create.call_count,1)
    def test_quota_auth_stop_transient_retries_bounded(self):
        for error in [RemoteError(401),RemoteError(429,'insufficient_quota')]:
            client=self.client([error])
            with self.assertRaises(RemoteError):structured_response(client,'i','input','phase',SCHEMA)
            self.assertEqual(client.responses.create.call_count,1)
        client=self.client([RemoteError(503)]*3)
        with patch('tools.structured_response.time.sleep'),self.assertRaises(RemoteError):structured_response(client,'i','input','phase',SCHEMA)
        self.assertEqual(client.responses.create.call_count,3)
    def test_credit_balance_exhausted_stops_first_attempt_and_keeps_safe_metadata(self) -> None:
        error=RemoteError(429,'credit_balance_exhausted')
        error.args=('private-token-and-error-message',)
        error.body={'error':{'type':'insufficient_quota','code':'credit_balance_exhausted','message':'private error body'}}
        client=self.client([error,response()])
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'RESULTS_RESPONSE_METRICS_DIR':folder,'RESULTS_RUN_ID':'synthetic-run','RESULTS_SOURCE_VERSION':'synthetic-version'}),patch('tools.structured_response.time.sleep') as sleep:
            with self.assertRaises(RemoteError):
                structured_response(client,'private instructions','private prompt','phase',SCHEMA)
            self.assertEqual(client.responses.create.call_count,1)
            sleep.assert_not_called()
            records=[json.loads(path.read_text(encoding='utf-8')) for path in Path(folder).glob('*.json')]
        self.assertEqual(len(records),1)
        self.assertEqual(records[0]['api_code'],'credit_balance_exhausted')
        self.assertEqual(records[0]['http_status'],429)
        self.assertNotIn('private',json.dumps(records))
        self.assertNotIn('body',records[0])

    def test_rate_limit_exceeded_still_retries_then_succeeds(self) -> None:
        client=self.client([RemoteError(429,'rate_limit_exceeded'),response()])
        with patch('tools.structured_response.time.sleep') as sleep:
            self.assertEqual(structured_response(client,'i','input','phase',SCHEMA),{})
        self.assertEqual(client.responses.create.call_count,2)
        sleep.assert_called_once_with(1)

    def test_truncation_at_ceiling_stops_and_metadata_contains_no_input(self):
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'RESULTS_RESPONSE_METRICS_DIR':folder}):
            client=self.client([response("incomplete","max_output_tokens")]*2)
            with self.assertRaises(ResponseIncomplete):structured_response(client,'i','secret input','phase',SCHEMA)
            self.assertEqual(client.responses.create.call_count,2)
            records=[json.loads(p.read_text()) for p in Path(folder).glob('*.json')]
            self.assertEqual(len(records),2);self.assertNotIn('secret',json.dumps(records))
    def test_checkpoint_resume_input_changes_and_scope(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'checkpoint.json';cache=AnalysisCheckpoint(path,'company-day');paid=Mock(return_value={'value':1})
            first=cache.call('bull',paid,{'input':1});first['value']=9
            resumed=AnalysisCheckpoint(path,'company-day')
            self.assertEqual(resumed.call('bull',paid,{'input':1}),{'value':1});self.assertEqual(paid.call_count,1)
            resumed.call('bull',paid,{'input':2});self.assertEqual(paid.call_count,2)
            with self.assertRaises(ValueError):AnalysisCheckpoint(path,'other-day')
    def test_failed_step_not_cached_completed_steps_survive(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'checkpoint.json';cache=AnalysisCheckpoint(path,'day');first=Mock(return_value={'ok':True});failed=Mock(side_effect=RuntimeError())
            cache.call('collect',first)
            with self.assertRaises(RuntimeError):cache.call('bear',failed)
            resumed=AnalysisCheckpoint(path,'day');resumed.call('collect',first)
            self.assertEqual(first.call_count,1);self.assertNotIn('bear',resumed.steps)
    def test_round_turn_keys_are_separate(self):
        with tempfile.TemporaryDirectory() as folder:
            cache=AnalysisCheckpoint(Path(folder)/'c.json','day');callback=Mock(return_value={'ok':True});turn=cache.bind(callback,'bull',rounds=True)
            turn({'current_round':1});turn({'current_round':2});turn({'current_round':1})
            self.assertEqual(callback.call_count,2)
    def test_real_graph_reuses_completed_turns(self):
        from agents.analysis_debate_agent import AnalysisDebateAgent
        agent=AnalysisDebateAgent(client=NS(responses=NS(create=Mock())))
        counts={"bull":0,"bear":0}
        def bull(state):counts["bull"]+=1;return {"bull_response":{}}
        def bear(state):counts["bear"]+=1;return {"bear_response":{}}
        def review(state):return {"moderator_review":{"continue_debate":False},"rounds":[*state.get("rounds",[]),{"round":state["current_round"]}]}
        with tempfile.TemporaryDirectory() as folder:
            cache=AnalysisCheckpoint(Path(folder)/'graph.json','day')
            for name,callback in [("create_agenda",lambda state:{"agenda":[]}),("bull_turn",bull),("bear_turn",bear),("moderator_review",review),("summarize",lambda state:{"moderator_summary":{}})]:
                setattr(agent,name,cache.bind(callback,name,rounds=True))
            graph=agent._build_graph()
            initial={"debate_input":"input","current_round":1,"max_rounds":3,"rounds":[]}
            self.assertEqual(len(graph.invoke(initial)["rounds"]),2)
            self.assertEqual(len(graph.invoke(initial)["rounds"]),2)
            self.assertEqual(counts,{"bull":2,"bear":2})
    def test_workflow_connects_stage_and_turn_checkpoints(self):
        from app.recoverable_debate_workflow import RecoverableDebateWorkflow
        def fake_init(owner):
            owner.evidence_workflow=NS(run=Mock(return_value={"context":1}))
            owner.historical_collector=NS(collect=Mock(return_value=[]))
            owner.regime_workflow=NS(run=Mock(return_value={}))
            owner.bull_agent=NS(analyze_with_context=Mock(return_value="bull"))
            owner.bear_agent=NS(analyze_with_context=Mock(return_value="bear"))
            owner.sentiment_agent=NS(analyze=Mock(return_value={}))
            owner.video_agent=NS(run_latest_short_topics=Mock(return_value={}))
            owner.navigator_agent=NS(analyze=Mock(return_value={}))
            owner.debate_agent=NS(**{name:Mock(return_value={}) for name in ["create_agenda","bull_turn","bear_turn","moderator_review","summarize"]},_build_graph=Mock(return_value="rebuilt"))
        with tempfile.TemporaryDirectory() as folder,patch('app.recoverable_debate_workflow.DebateWorkflow.__init__',fake_init):
            workflow=RecoverableDebateWorkflow(Path(folder)/'c.json','company','day')
            workflow.evidence_workflow.run('company');workflow.evidence_workflow.run('company')
            workflow.debate_agent.bull_turn({"current_round":1});workflow.debate_agent.bull_turn({"current_round":1})
            self.assertEqual(workflow.debate_agent.graph,'rebuilt')
            self.assertEqual(workflow.evidence_workflow.run('company'),{"context":1})
    def test_regime_prompt_excludes_chart_series(self):
        from agents.analysis_debate_agent import AnalysisDebateAgent
        text=AnalysisDebateAgent._build_input('company',{},'bull','bear',{},[],{'price_series':['private_series_marker'],'comparison':['keep comparison']},None)
        self.assertNotIn('private_series_marker',text);self.assertIn('keep comparison',text)

if __name__=='__main__':unittest.main()
