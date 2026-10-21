"""Reuse the existing workflow, caching completed local stages and debate turns."""
import hashlib
import json
import re
import sys
from pathlib import Path
from app.debate_workflow import DebateWorkflow
from tools.analysis_checkpoint import AnalysisCheckpoint
from config import MODEL_NAME

class RecoverableDebateWorkflow(DebateWorkflow):
    def __init__(self, checkpoint_path: Path, company: str, day: str) -> None:
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
        checkpoint=AnalysisCheckpoint(checkpoint_path,company+"|"+day+"|"+MODEL_NAME+"|"+signature)
        for obj,method,label in [(self.evidence_workflow,"run","collect"),(self.historical_collector,"collect","history"),(self.regime_workflow,"run","regime"),(self.bull_agent,"analyze_with_context","bull_initial"),(self.bear_agent,"analyze_with_context","bear_initial"),(self.sentiment_agent,"analyze","sentiment"),(self.video_agent,"run_latest_short_topics","shorts"),(self.navigator_agent,"analyze","navigation")]:
            setattr(obj,method,checkpoint.bind(getattr(obj,method),label))
        for name in ["create_agenda","bull_turn","bear_turn","moderator_review","summarize"]:
            setattr(self.debate_agent,name,checkpoint.bind(getattr(self.debate_agent,name),name,rounds=True))
        self.debate_agent.graph=self.debate_agent._build_graph()
