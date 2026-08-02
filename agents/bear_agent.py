from openai import OpenAI

from agents.analysis_axes import AnalysisAxis, select_analysis_axes
from agents.axis_analysis_prompt import AXIS_BEAR_SYSTEM_PROMPT
from agents.axis_analysis_schema import (
    PERSPECTIVE_ANALYSIS_SCHEMA,
    PerspectiveAnalysis,
    normalize_perspective_analysis,
    perspective_to_text,
)
from agents.bear_prompt import BEAR_SYSTEM_PROMPT
from agents.structured_response import create_structured_response
from app.bear_langgraph_workflow import BearGraphWorkflow
from config import MODEL_NAME, OPENAI_API_KEY


class BearAgent:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.workflow = BearGraphWorkflow()

    def analyze(
        self,
        company_name: str,
    ) -> tuple[str, dict, list[dict]]:
        workflow_result = self.workflow.run(company_name)

        financial_data = workflow_result["financial_data"]
        retrieved_chunks = workflow_result["retrieved_chunks"]
        report_context = workflow_result["report_context"]
        web_context = workflow_result["web_context"]

        axes = select_analysis_axes(company_name, financial_data)
        structured_result = self.analyze_structured_with_context(
            company_name=company_name,
            financial_data=financial_data,
            report_context=report_context,
            web_context=web_context,
            axes=axes,
        )
        result = self.structured_to_text(structured_result, axes)

        return (
            result,
            financial_data,
            retrieved_chunks,
        )

    def analyze_with_context(
        self,
        company_name: str,
        financial_data: dict,
        report_context: str,
        web_context: str,
    ) -> str:
        user_prompt = f"""
다음 기업을 Bear 관점에서 분석해줘.

기업명: {company_name}
티커: {financial_data["ticker"]}

현재 주가:
{financial_data["current_price"]}

주가 기준일:
{financial_data["price_date"]}

최근 연간 매출:
{financial_data["current_revenue"]}

전년도 매출:
{financial_data["previous_revenue"]}

매출 성장률:
{financial_data["revenue_growth"]}

최근 연간 영업이익:
{financial_data["current_operating_income"]}

전년도 영업이익:
{financial_data["previous_operating_income"]}

영업이익 성장률:
{financial_data["operating_income_growth"]}

최근 영업이익률:
{financial_data["current_operating_margin"]}

전년도 영업이익률:
{financial_data["previous_operating_margin"]}

[로컬 투자 리포트]

{report_context}

[최신 웹 검색 결과]

{web_context}

제공된 금융 데이터, 로컬 리포트,
최신 웹 검색 결과만 사용해서 분석해줘.

부정적인 투자 근거와 위험 요인만 분석하고,
검색 결과에 없는 사실은 추가하지 마.

웹 근거를 사용할 때는 반드시
출처와 게시일을 표시해.
""".strip()

        response = self.client.responses.create(
            model=MODEL_NAME,
            instructions=BEAR_SYSTEM_PROMPT,
            input=user_prompt,
        )

        return response.output_text

    def analyze_structured_with_context(
        self,
        company_name: str,
        financial_data: dict,
        report_context: str,
        web_context: str,
        axes: list[AnalysisAxis] | None = None,
        evidence_catalog: list[dict] | None = None,
    ) -> PerspectiveAnalysis:
        selected_axes = axes or select_analysis_axes(company_name, financial_data)
        result = create_structured_response(
            client=self.client,
            instructions=AXIS_BEAR_SYSTEM_PROMPT,
            input_data={
                "role": "bear",
                "company_name": company_name,
                "analysis_axes": selected_axes,
                "financial_data": financial_data,
                "local_reports": report_context,
                "web_sources": web_context,
                "allowed_evidence": evidence_catalog or [],
            },
            schema_name="bear_axis_analysis",
            schema=PERSPECTIVE_ANALYSIS_SCHEMA,
        )
        allowed_ids = {
            str(item.get("id", ""))
            for item in evidence_catalog or []
            if isinstance(item, dict)
            and item.get("id")
            and item.get("available", True)
        }
        return normalize_perspective_analysis(
            result,
            "bear",
            selected_axes,
            allowed_ids,
        )

    @staticmethod
    def structured_to_text(
        analysis: PerspectiveAnalysis,
        axes: list[AnalysisAxis],
    ) -> str:
        return perspective_to_text(analysis, axes)
