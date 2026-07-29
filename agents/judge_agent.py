import json

from openai import OpenAI

from agents.bear_agent import BearAgent
from agents.bull_agent import BullAgent
from agents.analysis_debate_agent import AnalysisDebateAgent
from agents.judge_prompt import JUDGE_SYSTEM_PROMPT
from agents.sentiment_agent import SentimentAgent
from app.comparison_workflow import ComparisonWorkflow
from config import MODEL_NAME, OPENAI_API_KEY


class JudgeAgent:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=OPENAI_API_KEY)

        self.workflow = ComparisonWorkflow()
        self.bull_agent = BullAgent()
        self.bear_agent = BearAgent()
        self.sentiment_agent = SentimentAgent()
        self.analysis_debate_agent = AnalysisDebateAgent()

    def analyze(
        self,
        company_name: str,
        video_debate: dict | None = None,
    ) -> dict:
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

        analysis_debate = self.analysis_debate_agent.run(
            company_name=company_name,
            financial_data=financial_data,
            bull_result=bull_result,
            bear_result=bear_result,
            sentiment_summary=sentiment_summary,
            video_summary=video_summary,
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

[뉴스 민심 분석]

{json.dumps(sentiment_summary, ensure_ascii=False, indent=2)}

[영상 관점별 요약]

{json.dumps(video_summary, ensure_ascii=False, indent=2) if video_summary else "사용하지 않음"}

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
- Bull Score와 Bear Score의 합은 100으로 작성한다.
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
            "sentiment_result": sentiment_result,
            "video_debate": video_debate,
            "analysis_debate": analysis_debate,
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
