import csv
import json
import tempfile
import unittest
from pathlib import Path

from tools.external_evaluation import import_scores, validate_report


class ExternalEvaluationTests(unittest.TestCase):
    def test_import_omits_raw_text_and_preserves_missing_scores(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            config={'framework_version':'fixture-only','dataset_name':'fixture','dataset_version':'v1','dataset_hash':'1'*64,'evaluator_model':'fixture-only','reference_origin':'synthetic','metric_config_hash':'2'*64}
            (root/'manifest.json').write_text(json.dumps(config),encoding='utf-8')
            with (root/'scores.csv').open('w',newline='',encoding='utf-8') as stream:
                writer=csv.writer(stream);writer.writerow(['case_id','faithfulness','context_recall','question']);writer.writerow(['original-id','1','','private text'])
            report=import_scores(root/'scores.csv',root/'manifest.json')
            self.assertIsNone(report['metrics']['context_recall'])
            self.assertEqual(report['metrics']['context_recall_count'],0)
            self.assertNotIn('private text',json.dumps(report))
            self.assertNotIn('original-id',json.dumps(report))
            report['metrics']['faithfulness']=.5
            with self.assertRaises(ValueError):validate_report(report)

    def test_unknown_report_is_rejected(self) -> None:
        with self.assertRaises(ValueError):validate_report({'scope':'external_rag'})


if __name__=='__main__':unittest.main()
