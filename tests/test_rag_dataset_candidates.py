import json
import tempfile
import unittest
from pathlib import Path

from tools.rag_benchmark import validate_dataset
from tools.rag_dataset_candidates import candidates, load_records

ROOT = Path(__file__).resolve().parent.parent


class RagDatasetCandidateTests(unittest.TestCase):
    def test_filters_company_status_and_cutoff(self) -> None:
        records = [
            {"filename": "a.pdf", "company": "삼성전자", "status": "ingested", "indexed_at": "x", "published_at": "2026-05-01"},
            {"filename": "future.pdf", "company": "삼성전자", "status": "ingested", "indexed_at": "x", "published_at": "2026-12-01"},
            {"filename": "nodate.pdf", "company": "삼성전자", "status": "ingested", "indexed_at": "x"},
            {"filename": "other.pdf", "company": "SK하이닉스", "status": "ingested", "indexed_at": "x", "published_at": "2026-05-01"},
            {"filename": "pending.pdf", "company": "삼성전자", "status": "approved", "published_at": "2026-05-01"},
        ]
        rows = candidates(records, company="삼성전자", as_of_date="2026-11-10")
        self.assertEqual([row["source"] for row in rows], ["a.pdf"])

    def test_reads_registry_dict(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            path.write_text(json.dumps({"d1": {"filename": "a.pdf"}}), encoding="utf-8")
            self.assertEqual(load_records(path), [{"filename": "a.pdf"}])

    def test_example_dataset_is_valid_and_marked_synthetic(self) -> None:
        data = json.loads((ROOT / "benchmarks/rag.dataset.example.json").read_text(encoding="utf-8"))
        validate_dataset(data)
        self.assertEqual(data["dataset_kind"], "synthetic")


if __name__ == "__main__":
    unittest.main()
