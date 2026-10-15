import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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


    def test_missing_public_manifest_never_contacts_storage(self) -> None:
        from frontend import export_results as exporter
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.dict(os.environ, {"RESULTS_SUPABASE_URL": "https://example.supabase.co", "RESULTS_SUPABASE_SECRET_KEY": "synthetic-test-key", "RESULTS_STORAGE_BUCKET": "analysis-results"}), patch("dotenv.load_dotenv", return_value=False), patch.object(exporter, "PUBLIC_MANIFEST", root / "missing.json"), patch("urllib.request.urlopen") as network:
                with self.assertRaises(ValueError): publisher.publish_results()
                network.assert_not_called()

    def test_empty_selection_never_replaces_index(self) -> None:
        calls = []
        with self.assertRaises(ValueError):
            publisher.publish_snapshot([], Path("."), lambda *args: calls.append(args))
        self.assertEqual(calls, [])

    def test_partial_upload_failure_does_not_publish_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); calls = []
            identifiers = ["a" * 16, "b" * 16]
            for identifier in identifiers:
                (root / (identifier + ".json")).write_text('{"company_name":"synthetic"}')
            def upload(name: str, content: bytes) -> None:
                calls.append(name)
                if len(calls) == 2: raise RuntimeError("synthetic interruption")
            with self.assertRaises(RuntimeError):
                publisher.publish_snapshot([{"id": identifier} for identifier in identifiers], root, upload)
            self.assertEqual(len(calls), 2)
            self.assertNotIn("index.json", calls)


if __name__ == '__main__':
    unittest.main()
