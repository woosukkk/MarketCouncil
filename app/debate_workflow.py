from typing import Any

from agents.analysis_debate_agent import AnalysisDebateAgent
from agents.bear_agent import BearAgent
from agents.bull_agent import BullAgent
from agents.sentiment_agent import SentimentAgent
from app.comparison_workflow import ComparisonWorkflow
from tools.evidence_catalog import EvidenceCatalog


class DebateWorkflow:
    def __init__(self) -> None:
        self.evidence_workflow = ComparisonWorkflow()
        self.bull_agent = BullAgent()
        self.bear_agent = BearAgent()
        self.sentiment_agent = SentimentAgent()
        self.debate_agent = AnalysisDebateAgent()

    def run(self, company_name: str) -> dict[str, Any]:
        print("\n[공통 근거 수집 시작]")
        context = self.evidence_workflow.run(company_name)
        print("[공통 근거 수집 완료]")

        financial_data = context["financial_data"]
        report_context = context["shared_report_context"]

        print("\n[상승 관점 최초 분석 시작]")
        bull_result = self.bull_agent.analyze_with_context(
            company_name=company_name,
            financial_data=financial_data,
            report_context=report_context,
            web_context=context["bull_web_context"],
        )
        print("[상승 관점 최초 분석 완료]")

        print("\n[하락 관점 최초 분석 시작]")
        bear_result = self.bear_agent.analyze_with_context(
            company_name=company_name,
            financial_data=financial_data,
            report_context=report_context,
            web_context=context["bear_web_context"],
        )
        print("[하락 관점 최초 분석 완료]")

        sentiment_result = self.sentiment_agent.analyze(
            company_name,
            source_data=context.get("source_data"),
        )
        sentiment_summary = {
            key: value
            for key, value in sentiment_result.items()
            if key != "source_documents"
        }
        retrieved_chunks = (
            context.get("bull_chunks", [])
            + context.get("bear_chunks", [])
            + context.get("filing_chunks", [])
        )
        evidence_catalog = EvidenceCatalog.build(
            financial_data=financial_data,
            retrieved_chunks=retrieved_chunks,
            web_documents=context.get("source_data", {}).get(
                "source_documents",
                [],
            ),
        )
        debate = self.debate_agent.run(
            company_name=company_name,
            financial_data=financial_data,
            bull_result=bull_result,
            bear_result=bear_result,
            sentiment_summary=sentiment_summary,
            evidence_catalog=evidence_catalog,
        )
        debate = EvidenceCatalog.resolve(debate, evidence_catalog)

        return {
            "company_name": company_name,
            "financial_data": financial_data,
            "bull_analysis": bull_result,
            "bear_analysis": bear_result,
            "sentiment_result": sentiment_result,
            "evidence_catalog": evidence_catalog,
            "evidence": {
                "bull_chunks": context.get("bull_chunks", []),
                "bear_chunks": context.get("bear_chunks", []),
                "filing_chunks": context.get("filing_chunks", []),
                "source_data": context.get("source_data", {}),
            },
            **debate,
        }
