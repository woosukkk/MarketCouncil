import json

from openai import OpenAI

from agents.bear_agent import BearAgent
from agents.bull_agent import BullAgent
from agents.analysis_debate_agent import AnalysisDebateAgent
from agents.judge_prompt import JUDGE_SYSTEM_PROMPT
from agents.neutral_agent import NeutralAgent
from agents.sentiment_agent import SentimentAgent
from app.comparison_workflow import ComparisonWorkflow
from config import MODEL_NAME, OPENAI_API_KEY


class JudgeAgent:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=OPENAI_API_KEY)

        self.workflow = ComparisonWorkflow()
        self.bull_agent = BullAgent()
        self.bear_agent = BearAgent()
        self.neutral_agent = NeutralAgent()
        self.sentiment_agent = SentimentAgent()
        self.analysis_debate_agent = AnalysisDebateAgent()

    def analyze(
        self,
        company_name: str,
        video_debate: dict | None = None,
        debate_mode: str = "none",
        existing_debate: dict | None = None,
    ) -> dict:
        if debate_mode not in {"none", "existing", "new"}:
            raise ValueError(f"지원하지 않는 토론 모드입니다: {debate_mode}")
        print("\n[공통 데이터 수집 시작]")

        context = self.workflow.run(company_name)

        print("[공통 데이터 수집 완료]")

        financial_data = context["financial_data"]

        print("\n[Bull Agent 분석 시작]")

        bull_result = self.bull_agent.analyze_with_context(
            company_name=company_name,
            financial_data=financial_data,
            report_context=context[
                "bull_report_context"
            ],
            web_context=context[
                "bull_web_context"
            ],
        )

        print("[Bull Agent 분석 완료]")

        print("\n[Bear Agent 분석 시작]")

        bear_result = self.bear_agent.analyze_with_context(
            company_name=company_name,
            financial_data=financial_data,
            report_context=context[
                "bear_report_context"
            ],
            web_context=context[
                "bear_web_context"
            ],
        )

        print("[Bear Agent 분석 완료]")

        print("\n[Neutral Agent 분석 시작]")

        neutral_result = self.neutral_agent.analyze_with_context(
            company_name=company_name,
            financial_data=financial_data,
            report_context=context["neutral_report_context"],
            web_context=context["neutral_web_context"],
        )

        print("[Neutral Agent 분석 완료]")

        print("\n[민심 Agent 분석 시작]")

        sentiment_result = self.sentiment_agent.analyze(
            company_name,
            source_data=context.get("source_data"),
        )

        print("[민심 Agent 분석 완료]")

        sentiment_summary = self._build_sentiment_summary(sentiment_result)
        video_summary = (
            self._build_video_summary(video_debate)
            if video_debate
            else None
        )

        analysis_debate: dict = {}
        debate_source = "none"
        if debate_mode == "existing":
            if not existing_debate:
                raise ValueError("적용할 최근 토론 결과가 없습니다.")
            analysis_debate = existing_debate
            debate_source = "existing"
        elif debate_mode == "new":
            analysis_debate = self.analysis_debate_agent.run(
                company_name=company_name,
                financial_data=financial_data,
                bull_result=bull_result,
                bear_result=bear_result,
                sentiment_summary=sentiment_summary,
                video_summary=video_summary,
            )
            debate_source = "newly_generated"

        debate_applied = bool(analysis_debate)
        debate_context = (
            self._build_debate_summary(analysis_debate)
            if debate_applied
            else "사용하지 않음"
        )

        print("\n[Judge Agent 비교 시작]")

        user_prompt = f"""
다음은 동일한 기업과 동일한 금융 데이터에 기반한
Bull 분석과 Bear 분석이다.

기업명: {company_name}

[공통 금융 데이터]

{financial_data}

[Bull 분석]

{bull_result}

[Bear 분석]

{bear_result}

[Neutral 기본 시나리오]

{neutral_result}

[뉴스 민심 분석]

{json.dumps(sentiment_summary, ensure_ascii=False, indent=2)}

[영상 관점별 요약]

{json.dumps(video_summary, ensure_ascii=False, indent=2) if video_summary else "사용하지 않음"}

[중재 토론 핵심 결과]

{json.dumps(debate_context, ensure_ascii=False, indent=2) if isinstance(debate_context, dict) else debate_context}

두 분석의 근거 구체성, 출처 신뢰도, 날짜,
금융 데이터와의 연결성을 비교해
최종 종합 의견을 작성해줘.

규칙:
- 근거 개수보다 품질을 우선한다.
- 같은 사건을 반복한 주장은 하나로 본다.
- 일반적인 면책 문구는 약한 근거로 평가한다.
- 출처와 날짜가 명확한 근거를 높게 평가한다.
- 뉴스 민심 비율은 보조 지표로만 사용한다.
- 기사 수만으로 Bull/Bear 점수를 결정하지 않는다.
- 영상 주장은 금융 데이터, RAG, 웹 근거와 일치할 때만 강한 근거로 평가한다.
- 토론 결과는 보조 검증 자료이며 원본 금융 데이터나 공시와 충돌하면 영향도를 낮춘다.
- 토론의 합의나 미해결 쟁점을 새로운 사실로 간주하지 않는다.
- Bull Score와 Bear Score의 합은 100으로 작성한다.
- Neutral은 독립 방향 점수가 아니라 Bull과 Bear를 비교하는 기준선으로 사용한다.
"""

        response = self.client.responses.create(
            model=MODEL_NAME,
            instructions=JUDGE_SYSTEM_PROMPT,
            input=user_prompt,
        )

        print("[Judge Agent 비교 완료]")

        return {
            "company_name": company_name,
            "financial_data": financial_data,
            "bull_result": bull_result,
            "bear_result": bear_result,
            "neutral_result": neutral_result,
            "sentiment_result": sentiment_result,
            "video_debate": video_debate,
            "analysis_debate": analysis_debate,
            "debate_applied": debate_applied,
            "debate_source": debate_source,
            "judge_result": response.output_text,
            "bull_chunks": context.get(
                "bull_chunks",
                [],
            ),
            "bear_chunks": context.get(
                "bear_chunks",
                [],
            ),
            "bull_web_context": context.get(
                "bull_web_context",
                "",
            ),
            "bear_web_context": context.get(
                "bear_web_context",
                "",
            ),
        }

    @staticmethod
    def _build_debate_summary(debate: dict) -> dict:
        rounds = debate.get("rounds", [])
        concessions = []
        for round_data in rounds:
            bull_issues = round_data.get("bull_response", {}).get("issues", [])
            bear_issues = round_data.get("bear_response", {}).get("issues", [])
            concessions.append({
                "round": round_data.get("round"),
                "bull_concessions": [
                    issue.get("concession", "")
                    for issue in bull_issues
                    if issue.get("concession")
                ],
                "bear_concessions": [
                    issue.get("concession", "")
                    for issue in bear_issues
                    if issue.get("concession")
                ],
            })
        summary = debate.get("moderator_summary", {}) or {}
        return {
            "created_at": debate.get("created_at", ""),
            "round_count": len(rounds),
            "issue_statuses": debate.get("issue_statuses", []),
            "agreements": summary.get("agreements", []),
            "unresolved_issues": summary.get("unresolved_issues", []),
            "required_evidence": summary.get("required_evidence", []),
            "moderator_summary": summary.get("summary", ""),
            "concessions": concessions,
            "stop_reason": debate.get("stop_reason", ""),
        }

    @staticmethod
    def _build_video_summary(
        video_debate: dict,
    ) -> dict:
        bull_video = video_debate.get("bull_video", {})
        bear_video = video_debate.get("bear_video", {})
        return {
            "company_name": video_debate.get("company_name", ""),
            "created_at": video_debate.get("created_at", ""),
            "bull_video_url": bull_video.get("video_url", ""),
            "bear_video_url": bear_video.get("video_url", ""),
            "bull_summary": video_debate.get("bull_summary", ""),
            "bear_summary": video_debate.get("bear_summary", ""),
        }

    @staticmethod
    def _build_sentiment_summary(
        sentiment_result: dict,
    ) -> dict:
        articles = sentiment_result.get("articles", [])
        key_articles = []

        for sentiment in ("positive", "negative"):
            key_articles.extend([
                article
                for article in articles
                if article.get("sentiment") == sentiment
            ][:2])

        return {
            "period": sentiment_result.get("period", ""),
            "total_count": sentiment_result.get("total_count", 0),
            "positive_count": sentiment_result.get("positive_count", 0),
            "negative_count": sentiment_result.get("negative_count", 0),
            "neutral_count": sentiment_result.get("neutral_count", 0),
            "positive_ratio": sentiment_result.get("positive_ratio", 0.0),
            "negative_ratio": sentiment_result.get("negative_ratio", 0.0),
            "neutral_ratio": sentiment_result.get("neutral_ratio", 0.0),
            "sentiment_score": sentiment_result.get("sentiment_score", 0.0),
            "summary": sentiment_result.get("summary", ""),
            "key_articles": key_articles,
        }
