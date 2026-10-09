import unittest
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


if __name__ == "__main__":
    unittest.main()
