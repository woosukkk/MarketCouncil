import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

from app.debate_workflow import DebateWorkflow
from tools.analysis_checkpoint import AnalysisCheckpoint


class ParallelAnalysisTests(unittest.TestCase):
    def workflow(self, bull: object, bear: object) -> DebateWorkflow:
        workflow=DebateWorkflow.__new__(DebateWorkflow)
        workflow.evidence_workflow=NS(run=Mock(return_value={
            'financial_data':{'ticker':'TEST'},'shared_report_context':'same reports',
            'bull_web_context':'bull sources','bear_web_context':'bear sources'}))
        workflow.historical_collector=NS(collect=Mock(return_value=[]))
        workflow.regime_workflow=NS(run=Mock(return_value={}))
        workflow.bull_agent=NS(analyze_with_context=bull)
        workflow.bear_agent=NS(analyze_with_context=bear)
        workflow.sentiment_agent=NS(analyze=Mock(return_value={}))
        workflow.video_agent=NS(run_latest_short_topics=Mock(return_value={}))
        workflow.debate_agent=NS(run=Mock(return_value={'rounds':[]}))
        workflow.navigator_agent=NS(analyze=Mock(return_value={}))
        return workflow

    def test_initial_views_overlap_and_keep_role_results(self) -> None:
        barrier=threading.Barrier(2)
        def analyze(label: str, **kwargs: object) -> str:
            barrier.wait(timeout=5)
            return label
        bull=Mock(side_effect=lambda **kw:analyze('bull result',**kw))
        bear=Mock(side_effect=lambda **kw:analyze('bear result',**kw))
        result=self.workflow(bull,bear).run('test company')
        self.assertEqual(result['bull_analysis'],'bull result')
        self.assertEqual(result['bear_analysis'],'bear result')
        self.assertEqual(bull.call_args.kwargs['web_context'],'bull sources')
        self.assertEqual(bear.call_args.kwargs['web_context'],'bear sources')

    def test_concurrent_checkpoint_writes_preserve_all_distinct_stages(self) -> None:
        barrier=threading.Barrier(4)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'checkpoint.json'
            cache=AnalysisCheckpoint(path,'same scope')
            def completed(value: int) -> int:
                barrier.wait(timeout=5)
                return value
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures=[executor.submit(cache.call,str(i),completed,i) for i in range(12)]
                self.assertEqual([f.result() for f in futures],list(range(12)))
            stored=json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(len(stored['steps']),12)
            resumed=AnalysisCheckpoint(path,'same scope')
            for i in range(12):
                callback=Mock(side_effect=AssertionError('completed stage repeated'))
                self.assertEqual(resumed.call(str(i),callback,i),i)
                callback.assert_not_called()

    def test_failure_propagates_but_other_completed_view_can_resume(self) -> None:
        barrier=threading.Barrier(2)
        def failed(**kwargs: object) -> str:
            barrier.wait(timeout=5)
            raise RuntimeError('upstream unavailable')
        def completed(**kwargs: object) -> str:
            barrier.wait(timeout=5)
            return 'saved bear'
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'checkpoint.json'
            cache=AnalysisCheckpoint(path,'scope')
            workflow=self.workflow(cache.bind(failed,'bull'),cache.bind(completed,'bear'))
            with self.assertRaisesRegex(RuntimeError,'upstream unavailable'):
                workflow.run('test company')
            resumed=AnalysisCheckpoint(path,'scope')
            self.assertNotIn('bull',resumed.steps)
            self.assertIn('bear',resumed.steps)
            unused=Mock(side_effect=AssertionError('bear repeated'))
            workflow.bull_agent.analyze_with_context=resumed.bind(lambda **kw:'new bull','bull')
            workflow.bear_agent.analyze_with_context=resumed.bind(unused,'bear')
            result=workflow.run('test company')
            self.assertEqual(result['bear_analysis'],'saved bear')
            unused.assert_not_called()


if __name__=='__main__':unittest.main()
