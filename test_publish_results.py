import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('publisher', Path(__file__).with_name('publish_results.py'))
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


class PublishingTest(unittest.TestCase):
    def test_documents_precede_index_and_keep_existing_versions(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            identifier = 'a' * 16
            (root / f'{identifier}.json').write_text('{"company_name":"test"}')
            calls = []
            publisher.publish_snapshot([{'id': identifier}], root, lambda name, body: calls.append((name, body)))
            self.assertEqual(calls[-1][0], 'index.json')
            self.assertEqual(json.loads(calls[-1][1])[0]['id'] + '.json', calls[0][0])
            failed = []
            def fail(name, body):
                failed.append(name)
                raise RuntimeError('offline')
            with self.assertRaises(RuntimeError):
                publisher.publish_snapshot([{'id': identifier}], root, fail)
            self.assertNotIn('index.json', failed)

    def test_path_traversal_rejected(self):
        with self.assertRaises(ValueError):
            publisher.publish_snapshot([{'id': '../secret'}], Path('.'), lambda *args: None)


if __name__ == '__main__':
    unittest.main()
