import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from frontend import export_results as exporter
from frontend.export_results import compact_evidence


class ResultExportTests(unittest.TestCase):
    def test_only_cited_excerpt_and_metadata_leave_local_archive(self) -> None:
        evidence = {"exact_quote": "Used excerpt", "title": "Report", "page_number": 4,
                    "source_url": "https://example.com/report.pdf", "context_text": "Long source body",
                    "document_id": "local-file", "chunk_id": "vector", "raw_document": "Full PDF"}
        data = {"rounds": [{"bull_response": {"issues": [{"claim": "Analysis", "evidence": [evidence]}]}}]}
        result = compact_evidence(data)
        exported = result["rounds"][0]["bull_response"]["issues"][0]
        self.assertEqual(exported["claim"], "Analysis")
        self.assertEqual(exported["evidence"][0], {key: evidence[key] for key in
                         ("exact_quote", "title", "page_number", "source_url")})
        self.assertIn("context_text", evidence)
        self.assertEqual(compact_evidence({"evidence": ["legacy quote"]}), {"evidence": ["legacy quote"]})


class PublicSelectionTests(unittest.TestCase):
    def manifest(self, root: Path, entries: list) -> Path:
        path = root / "public-results.json"
        path.write_text(json.dumps({"results": entries}), encoding="utf-8")
        return path

    def result(self, source: Path) -> tuple[Path, dict]:
        path = source / "Example" / "analysis_debate_public.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"company_name": "Example", "created_at": "2026-10-15", "rounds": [], "api_key": "not-for-export"}), encoding="utf-8")
        return path, {"path": path.relative_to(source).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def test_only_approved_file_is_exported_without_scanning_private_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root / "archive"
            _, entry = self.result(source)
            (source / "analysis_debate_private.json").write_text("PRIVATE: not even valid JSON", encoding="utf-8")
            manifest = self.manifest(root, [entry])
            with patch.object(exporter, "ROOT", root / "frontend"), patch.object(exporter, "SOURCE", source), patch.object(Path, "rglob", side_effect=AssertionError("must not scan")):
                exporter.export(manifest)
            output = root / "frontend" / "public" / "data"
            records = json.loads((output / "index.json").read_text(encoding="utf-8"))
            self.assertEqual(len(records), 1)
            payload = json.loads((output / (records[0]["id"] + ".json")).read_text(encoding="utf-8"))
            self.assertNotIn("api_key", payload)
            self.assertEqual(payload["company_name"], "Example")
            self.assertEqual(len(list(output.glob("*.json"))), 2)

    def test_missing_or_empty_selection_preserves_existing_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); output = root / "frontend" / "public" / "data"
            output.mkdir(parents=True); index = output / "index.json"
            index.write_text("previous public index", encoding="utf-8")
            missing = root / "missing-manifest.json"
            empty = self.manifest(root, [])
            with patch.object(exporter, "ROOT", root / "frontend"), patch.object(exporter, "SOURCE", root / "archive"), patch.object(exporter, "PUBLIC_MANIFEST", missing):
                with self.assertRaises(ValueError): exporter.export()
                with self.assertRaises(ValueError): exporter.export(empty)
            self.assertEqual(index.read_text(encoding="utf-8"), "previous public index")

    def test_modified_or_duplicate_result_is_rejected_before_export(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root / "archive"
            path, entry = self.result(source)
            with patch.object(exporter, "SOURCE", source), patch.object(exporter, "ROOT", root / "frontend"):
                with self.assertRaises(ValueError): exporter.export(self.manifest(root, [entry, entry]))
                path.write_text("changed after approval", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "changed after public approval"):
                    exporter.export(self.manifest(root, [entry]))
            self.assertFalse((root / "frontend").exists())

    def test_traversal_absolute_and_invalid_manifest_paths_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root / "archive"
            _, entry = self.result(source)
            paths = ["../analysis_debate_other.json", "/analysis_debate_other.json", str(root / "analysis_debate_other.json"), "Example\\analysis_debate_public.json", "Example/./analysis_debate_public.json", "Example//analysis_debate_public.json", "Example/*.json", "Example/missing.json"]
            with patch.object(exporter, "SOURCE", source):
                for name in paths:
                    with self.subTest(name=name), self.assertRaises(ValueError):
                        exporter.selected_results(self.manifest(root, [{**entry, "path": name}]))
                for bad in [{"path": entry["path"]}, {**entry, "sha256": "not-a-hash"}, {**entry, "extra": True}]:
                    with self.subTest(entry=bad), self.assertRaises(ValueError):
                        exporter.selected_results(self.manifest(root, [bad]))

    def test_resolved_path_cannot_escape_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root / "archive"
            _, entry = self.result(source)
            manifest = self.manifest(root, [entry])
            outside = root / "analysis_debate_outside.json"
            with patch.object(exporter, "SOURCE", source), patch.object(Path, "resolve", side_effect=[source, outside]):
                with self.assertRaises(ValueError): exporter.selected_results(manifest)


if __name__ == "__main__":
    unittest.main()
