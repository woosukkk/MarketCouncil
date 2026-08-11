from typing import Any

from agents.analysis_debate_agent import AnalysisDebateAgent
from agents.bear_agent import BearAgent
from agents.bull_agent import BullAgent
from agents.debate_navigator_agent import DebateNavigatorAgent
from agents.sentiment_agent import SentimentAgent
from app.comparison_workflow import ComparisonWorkflow
from app.regime_workflow import RegimeWorkflow
from tools.evidence_catalog import EvidenceCatalog
from tools.regime_context import build_regime_context


class DebateWorkflow:
    def __init__(self) -> None:
        self.evidence_workflow = ComparisonWorkflow()
        self.bull_agent = BullAgent()
        self.bear_agent = BearAgent()
        self.sentiment_agent = SentimentAgent()
        self.debate_agent = AnalysisDebateAgent()
        self.navigator_agent = DebateNavigatorAgent()
        self.regime_workflow = RegimeWorkflow()

    def run(self, company_name: str) -> dict[str, Any]:
        print("\n[공통 근거 수집 시작]")
        context = self.evidence_workflow.run(company_name)
        print("[공통 근거 수집 완료]")

        financial_data = context["financial_data"]
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
        try:
            regime_analysis = self.regime_workflow.run(
                company_name,
                str(financial_data.get("ticker", "")),
                evidence_catalog,
            )
        except RuntimeError as error:
            print(f"[WARN] {error}")
            regime_analysis = {
                "schema_version": 1,
                "company_name": company_name,
                "ticker": financial_data.get("ticker", ""),
                "regimes": {},
                "comparison": [],
                "reasons": {"past_bull": [], "recent_bear": []},
                "limitations": [str(error)],
            }
        report_context = (
            f"{context['shared_report_context']}\n\n"
            "[시계열 시장 국면 비교]\n"
            f"{build_regime_context(regime_analysis)}"
        )

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
        debate = self.debate_agent.run(
            company_name=company_name,
            financial_data=financial_data,
            bull_result=bull_result,
            bear_result=bear_result,
            sentiment_summary=sentiment_summary,
            evidence_catalog=EvidenceCatalog.for_prompt(evidence_catalog),
            regime_analysis=regime_analysis,
        )
        debate = EvidenceCatalog.resolve(debate, evidence_catalog)
        try:
            debate["navigation"] = self.navigator_agent.analyze(debate)
        except RuntimeError as error:
            print(f"[WARN] {error}")
            debate["navigation"] = {}

        return {
            "company_name": company_name,
            "financial_data": financial_data,
            "bull_analysis": bull_result,
            "bear_analysis": bear_result,
            "sentiment_result": sentiment_result,
            "evidence_catalog": evidence_catalog,
            "regime_analysis": regime_analysis,
            "evidence": {
                "bull_chunks": context.get("bull_chunks", []),
                "bear_chunks": context.get("bear_chunks", []),
                "filing_chunks": context.get("filing_chunks", []),
                "source_data": context.get("source_data", {}),
            },
            **debate,
        }
