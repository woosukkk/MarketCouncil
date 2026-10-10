import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tools.rag_benchmark import evaluate, score, validate_dataset
from tools.run_metrics import measure_analysis

class PerformanceTests(unittest.TestCase):
    def setUp(self):
        self.case={"id":"q1","query":"question","company":"삼성전자","as_of_date":"2026-01-01","expected":[{"source":"a","chunk_id":1},{"source":"b","chunk_id":2}]}
    def test_recall_rank_and_isolation_checks(self):
        rows=[{"source":"unrelated","metadata":{"company":"다른기업","published_timestamp":2000000000}},{"source":"a","chunk_id":1,"metadata":{"company":"삼성전자"}},{"source":"a","chunk_id":1}]
        result=score(self.case,rows)
        self.assertEqual(result["recall"],.5)
        self.assertEqual(result["mrr"],.5)
        self.assertEqual(result["mixed_company"],1)
        self.assertEqual(result["unknown_company"],1)
        self.assertEqual(result["future_sources"],1)
        self.assertEqual(score(self.case,[])["mrr"],0)
    def test_ground_truth_required_and_fixed_filters(self):
        with self.assertRaises(ValueError):validate_dataset({"name":"test","cases":[{**self.case,"expected":[]}]})
        with self.assertRaises(ValueError):validate_dataset({"name":"test","cases":[self.case,self.case]})
        calls=[]
        def search(**kwargs):calls.append(kwargs);return [{"source":"a","chunk_id":1}]
        report=evaluate({"name":"unit-test-only","cases":[self.case]},search,5,3)
        self.assertEqual(report["settings"]["case_count"],1)
        self.assertEqual(len(report["cases"]),3)
        self.assertTrue(all(x["company_name"]=="삼성전자" and x["as_of_date"]=="2026-01-01" for x in calls))
        self.assertNotIn("query",json.dumps(report))
    def test_measurement_failure_preserves_error_and_no_secrets(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)
            self.assertEqual(measure_analysis("삼성전자",lambda:42,path),42)
            def fail():raise RuntimeError("private content")
            with self.assertRaises(RuntimeError):measure_analysis("삼성전자",fail,path)
            records=[json.loads(x.read_text(encoding="utf-8")) for x in path.glob('*.json')]
            self.assertEqual({x["status"] for x in records},{"success","failed"})
            self.assertNotIn("private content",json.dumps(records))
            with patch('tools.run_metrics.Path.mkdir',side_effect=OSError):
                self.assertEqual(measure_analysis("삼성전자",lambda:7,path),7)
