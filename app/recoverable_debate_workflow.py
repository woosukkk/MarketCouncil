"""Reuse the existing workflow, caching completed local stages and debate turns."""
import hashlib
import json
import re
import os
import sys
from pathlib import Path
from app.debate_workflow import DebateWorkflow
from tools.analysis_checkpoint import AnalysisCheckpoint
from config import MODEL_NAME

class RecoverableDebateWorkflow(DebateWorkflow):
    def __init__(self, checkpoint_path: Path, company: str, day: str, *, ticker: str | None = None, corpus_hash: str | None = None) -> None:
        root=Path(__file__).resolve().parent.parent
        names = [
            'app/debate_workflow.py',
            'app/comparison_workflow.py',
            'rag/retriever.py',
            'agents/analysis_debate_agent.py',
            'agents/bull_agent.py',
            'agents/bull_prompt.py',
            'agents/bear_agent.py',
            'agents/bear_prompt.py',
            'agents/sentiment_agent.py',
            'agents/sentiment_prompt.py',
            'agents/debate_navigator_agent.py',
            'agents/moderator_agent.py',
            'agents/analysis_debate_prompt.py',
            'agents/moderator_prompt.py',
            'tools/structured_response.py',
            'tools/debate_payload.py',
            'tools/analysis_checkpoint.py',
            'tools/evidence_catalog.py',
            'tools/evidence_text.py',
            'tools/crawl4ai_extractor.py',
            'tools/source_collector.py',
            'tools/citation_quality.py',
            'tools/evidence_dates.py',
            'tools/financial_data.py',
            'tools/quality_valuation.py',
            'agents/debate_navigator_prompt.py',
            'agents/video_debate_agent.py',
            'agents/video_debate_prompt.py',
            'agents/video_topic_prompt.py',
            'app/regime_workflow.py',
            'agents/regime_reason_agent.py',
            'agents/regime_reason_prompt.py',
            'tools/regime_context.py',
            'tools/market_regime.py',
            'tools/historical_evidence_collector.py',
            'tools/open_source_web_collector.py',
            'tools/searxng_search.py',
            'tools/source_collector_prompt.py',
            'tools/source_collector_schema.py',
            'app/evidence_preflight.py',
            'tools/company_profiles.py',
            'tools/evidence_readiness.py',
            'tools/company_evidence_collector.py',
            'tools/official_ir_collector.py',
            'tools/issuer_filings_collector.py',
        ]
        if getattr(sys, "frozen", False):
            from desktop.preferences import VERSION
            metadata = json.loads((Path(sys._MEIPASS) / "release-build.json").read_text(encoding="utf-8"))
            commit = metadata.get("source_commit") if isinstance(metadata, dict) else None
            version = metadata.get("version") if isinstance(metadata, dict) else None
            if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit) or version != VERSION:
                raise ValueError("Invalid desktop build metadata")
            signature = hashlib.sha256(("desktop|" + version + "|" + commit).encode()).hexdigest()
        else:
            signature=hashlib.sha256(b"".join((root/name).read_bytes() for name in names)).hexdigest()
        super().__init__()
        self._evidence_target = (company, ticker, corpus_hash)
        self._checkpoint_base = Path(checkpoint_path)
        self._checkpoint_scope = company+"|"+day+"|"+MODEL_NAME+"|"+signature
        self._original_targets = []
        initial_scope = self._checkpoint_scope+"|"+(ticker or "")+"|"+(corpus_hash or "unprepared")
        self._active_checkpoint_path = self._scoped_path(initial_scope)
        checkpoint=AnalysisCheckpoint(self._active_checkpoint_path, initial_scope)
        for obj,method,label in [(self.evidence_workflow,"run","collect"),(self.historical_collector,"collect","history"),(self.regime_workflow,"run","regime"),(self.bull_agent,"analyze_with_context","bull_initial"),(self.bear_agent,"analyze_with_context","bear_initial"),(self.sentiment_agent,"analyze","sentiment"),(self.video_agent,"run_latest_short_topics","shorts"),(self.navigator_agent,"analyze","navigation")]:
            self._original_targets.append((obj,method,label,getattr(obj,method),False))
            setattr(obj,method,checkpoint.bind(getattr(obj,method),label))
        for name in ["create_agenda","bull_turn","bear_turn","moderator_review","summarize"]:
            self._original_targets.append((self.debate_agent,name,name,getattr(self.debate_agent,name),True))
            setattr(self.debate_agent,name,checkpoint.bind(getattr(self.debate_agent,name),name,rounds=True))
        self.debate_agent.graph=self.debate_agent._build_graph()


    def _scoped_path(self, scope: str) -> Path:
        identity = hashlib.sha256(scope.encode()).hexdigest()[:16]
        return self._checkpoint_base.with_name(self._checkpoint_base.stem+"-"+identity+self._checkpoint_base.suffix)

    def run(self, company_name: str) -> dict:
        from app.evidence_preflight import require_company_ready, bind_prepared_corpus, reset_prepared_corpus
        from tools.company_lookup import resolve_ticker
        company, selected_ticker, expected_hash = self._evidence_target
        if company_name != company:
            raise ValueError("체크포인트의 기업이 다릅니다.")
        ticker = selected_ticker or resolve_ticker(company, os.getenv("MARKETCOUNCIL_TICKER"))
        _, report = require_company_ready(company, ticker, refresh=False)
        if expected_hash and expected_hash != report["corpus_hash"]:
            raise ValueError("분석 준비 이후 근거 묶음이 바뀌었습니다. 이전 결과를 재사용하지 않습니다.")
        scope = self._checkpoint_scope+"|"+ticker+"|"+report["corpus_hash"]
        self._active_checkpoint_path = self._scoped_path(scope)
        checkpoint = AnalysisCheckpoint(self._active_checkpoint_path, scope)
        for owner, name, label, original, rounds in self._original_targets:
            setattr(owner, name, checkpoint.bind(original, label, rounds=rounds))
        self.debate_agent.graph = self.debate_agent._build_graph()
        token = bind_prepared_corpus(report)
        try:
            result = super().run(company_name)
            result["readiness_report"] = report
            return result
        finally:
            reset_prepared_corpus(token)
