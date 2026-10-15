"""Reuse the existing workflow, caching completed local stages and debate turns."""
import hashlib
from pathlib import Path
from app.debate_workflow import DebateWorkflow
from tools.analysis_checkpoint import AnalysisCheckpoint
from config import MODEL_NAME

class RecoverableDebateWorkflow(DebateWorkflow):
    def __init__(self, checkpoint_path: Path, company: str, day: str) -> None:
        super().__init__()
        root=Path(__file__).resolve().parent.parent
        names=["app/debate_workflow.py","agents/analysis_debate_agent.py","agents/moderator_agent.py","agents/analysis_debate_prompt.py","agents/moderator_prompt.py","tools/structured_response.py","tools/evidence_catalog.py","tools/citation_quality.py","tools/evidence_dates.py","tools/financial_data.py","tools/quality_valuation.py"]
        signature=hashlib.sha256(b"".join((root/name).read_bytes() for name in names)).hexdigest()
        checkpoint=AnalysisCheckpoint(checkpoint_path,company+"|"+day+"|"+MODEL_NAME+"|"+signature)
        for obj,method,label in [(self.evidence_workflow,"run","collect"),(self.historical_collector,"collect","history"),(self.regime_workflow,"run","regime"),(self.bull_agent,"analyze_with_context","bull_initial"),(self.bear_agent,"analyze_with_context","bear_initial"),(self.sentiment_agent,"analyze","sentiment"),(self.video_agent,"run_latest_short_topics","shorts"),(self.navigator_agent,"analyze","navigation")]:
            setattr(obj,method,checkpoint.bind(getattr(obj,method),label))
        for name in ["create_agenda","bull_turn","bear_turn","moderator_review","summarize"]:
            setattr(self.debate_agent,name,checkpoint.bind(getattr(self.debate_agent,name),name,rounds=True))
        self.debate_agent.graph=self.debate_agent._build_graph()
