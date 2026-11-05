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


    def test_malformed_readiness_reports_raise_value_error_at_any_payload_depth(self) -> None:
        for report in ([],["ready"],"private-invalid-report",0,1.5,False,{"status":"ready"}):
            for data in ({"readiness_report":report},{"financial_data":{"ticker":"AAPL","readiness_report":report}}):
                with self.subTest(report_type=type(report).__name__,nested="financial_data" in data):
                    with self.assertRaises(ValueError) as error:compact_evidence(data)
                    self.assertNotIn("private-invalid-report",str(error.exception))
        self.assertEqual(compact_evidence({"readiness_report":None}),{"readiness_report":None})


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

    def test_malformed_approved_report_preserves_public_index_and_existing_payloads(self) -> None:
        for report in ([],"invalid-report",{"status":"ready"}):
            with self.subTest(report_type=type(report).__name__),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);source=root/"archive";path,entry=self.result(source)
                data=json.loads(path.read_text(encoding="utf-8"));data["readiness_report"]=report
                path.write_text(json.dumps(data),encoding="utf-8")
                entry["sha256"]=hashlib.sha256(path.read_bytes()).hexdigest()
                manifest=self.manifest(root,[entry])
                output=root/"frontend"/"public"/"data";output.mkdir(parents=True)
                index=output/"index.json";index.write_text("previous public index",encoding="utf-8")
                old=output/"previous.json";old.write_text("previous selected payload",encoding="utf-8")
                with patch.object(exporter,"ROOT",root/"frontend"),patch.object(exporter,"SOURCE",source):
                    with self.assertRaises(ValueError):exporter.export(manifest)
                self.assertEqual(index.read_text(encoding="utf-8"),"previous public index")
                self.assertEqual(old.read_text(encoding="utf-8"),"previous selected payload")
                self.assertEqual({file.name for file in output.iterdir()},{"index.json","previous.json"})

    def test_valid_report_for_another_issuer_is_rejected_before_public_files_change(self) -> None:
        from tests.test_evidence_preflight import AS_OF, primary_manifest
        from tools.evidence_readiness import evaluate_readiness
        apple=evaluate_readiness(primary_manifest(),AS_OF)
        other=evaluate_readiness(primary_manifest("Microsoft Corporation","MSFT"),AS_OF)
        for nested in (False,True):
            with self.subTest(nested=nested),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);source=root/"archive";path,entry=self.result(source)
                data={"company_name":"Apple Inc.","created_at":AS_OF,"financial_data":{"ticker":"AAPL"},"rounds":[]}
                if nested:
                    data["readiness_report"]=apple
                    data["financial_data"]["readiness_report"]=other
                else:data["readiness_report"]=other
                path.write_text(json.dumps(data),encoding="utf-8")
                entry["sha256"]=hashlib.sha256(path.read_bytes()).hexdigest()
                manifest=self.manifest(root,[entry])
                output=root/"frontend"/"public"/"data";output.mkdir(parents=True)
                index=output/"index.json";index.write_text("previous public index",encoding="utf-8")
                previous=output/"previous.json";previous.write_text("previous payload",encoding="utf-8")
                with patch.object(exporter,"ROOT",root/"frontend"),patch.object(exporter,"SOURCE",source):
                    with self.assertRaises(ValueError):exporter.export(manifest)
                self.assertEqual(index.read_text(encoding="utf-8"),"previous public index")
                self.assertEqual(previous.read_text(encoding="utf-8"),"previous payload")
                self.assertEqual({file.name for file in output.iterdir()},{"index.json","previous.json"})

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
