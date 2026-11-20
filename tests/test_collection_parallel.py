"""Offline check that local document search and web collection run side by side."""
import os
import tempfile
import threading
import time
import unittest
from contextvars import ContextVar
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("OPENAI_API_KEY", "offline-test-key")

from app.comparison_workflow import ComparisonWorkflow
from tools.run_metrics import measure_analysis

BOUND: ContextVar[str | None] = ContextVar("test_bound_corpus", default=None)


class CollectionParallelTests(unittest.TestCase):
    def workflow(self, barrier: threading.Barrier, seen: dict) -> ComparisonWorkflow:
        workflow = object.__new__(ComparisonWorkflow)

        def filings(company: str, top_k: int) -> list[dict]:
            seen["filing_corpus"] = BOUND.get()
            barrier.wait()  # only passes when the web branch is running at the same time
            return [{"source": "filing.pdf", "chunk_id": "1", "text": "공시 본문"}]

        def collect(company: str, ticker: str | None = None) -> dict:
            seen["web_corpus"], seen["web_ticker"] = BOUND.get(), ticker
            barrier.wait()
            time.sleep(0.05)
            return {"articles": [{"title": "기사", "use_as_evidence": True}]}

        workflow.bull_tools = SimpleNamespace(
            get_company_financials=lambda company: {"ticker": "005930.KS", "financial_facts": {}},
            search_regulatory_filings=filings,
            search_company_reports=lambda company, top_k: [{"source": "bull.pdf", "chunk_id": "2", "text": "리포트"}],
        )
        workflow.bear_tools = SimpleNamespace(
            search_company_reports=lambda company, top_k: [{"source": "bear.pdf", "chunk_id": "3", "text": "리포트"}],
        )
        workflow.source_collector = SimpleNamespace(collect=collect)

        def resolve(source_data: dict, retrieved_chunks: list[dict]) -> dict:
            seen["resolved_with"] = sorted(chunk["source"] for chunk in retrieved_chunks)
            seen["resolved_articles"] = len(source_data.get("articles", []))
            return {**source_data, "evidence_bundle": {"ok": True}}

        workflow.evidence_resolver = SimpleNamespace(resolve=resolve)
        workflow.graph = workflow._build_graph()
        return workflow

    def test_filing_search_and_web_collection_overlap_and_join_before_resolution(self) -> None:
        seen: dict = {}
        workflow = self.workflow(threading.Barrier(2, timeout=10), seen)
        token = BOUND.set("prepared-corpus")
        try:
            with tempfile.TemporaryDirectory(prefix="marketcouncil-parallel-") as folder:
                state = measure_analysis("삼성전자", lambda: workflow.graph.invoke({"company_name": "삼성전자"}), Path(folder))
        finally:
            BOUND.reset(token)
        # Both branches saw the corpus bound by the caller, so worker threads keep the context.
        self.assertEqual((seen["filing_corpus"], seen["web_corpus"], seen["web_ticker"]), ("prepared-corpus", "prepared-corpus", "005930.KS"))
        # Resolution ran once, after both branches, with every local chunk and the web articles.
        self.assertEqual(seen["resolved_with"], ["bear.pdf", "bull.pdf", "filing.pdf"])
        self.assertEqual(seen["resolved_articles"], 1)
        self.assertEqual(state["evidence_bundle"], {"ok": True})
        self.assertIn("공시 본문", state["shared_report_context"])
        self.assertIn("기사", state["shared_web_context"])

    def test_a_branch_failure_stops_the_collection(self) -> None:
        seen: dict = {}
        workflow = self.workflow(threading.Barrier(1), seen)

        def broken(company: str, ticker: str | None = None) -> dict:
            raise RuntimeError("web collection failed")

        workflow.source_collector = SimpleNamespace(collect=broken)
        workflow.graph = workflow._build_graph()
        with self.assertRaisesRegex(RuntimeError, "web collection failed"):
            workflow.graph.invoke({"company_name": "삼성전자"})
        self.assertNotIn("resolved_with", seen)


if __name__ == "__main__":
    unittest.main()
