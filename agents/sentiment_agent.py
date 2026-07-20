import json
from typing import Any

from openai import OpenAI

from agents.sentiment_prompt import SENTIMENT_SYSTEM_PROMPT
from config import MODEL_NAME, OPENAI_API_KEY


class SentimentAgent:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=OPENAI_API_KEY)

    def analyze(self, company_name: str) -> dict[str, Any]:
        response = self.client.responses.create(
            model=MODEL_NAME,
            instructions=SENTIMENT_SYSTEM_PROMPT,
            tools=[
                {
                    "type": "web_search",
                    "search_context_size": "medium",
                }
            ],
            input=(
                f"현재 날짜를 기준으로 {company_name} 관련 최신 주요 뉴스를 "
                "중립적으로 검색하고 뉴스 민심을 분석해줘."
            ),
        )

        result = self._parse_json(response.output_text)
        return self._normalize(result)

    @staticmethod
    def _parse_json(output_text: str) -> dict[str, Any]:
        text = output_text.strip()

        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1]).strip()

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as error:
            raise ValueError(
                "민심 에이전트가 올바른 JSON을 반환하지 않았습니다."
            ) from error

        if not isinstance(parsed, dict):
            raise ValueError("민심 분석 결과는 JSON 객체여야 합니다.")

        return parsed

    @staticmethod
    def _normalize(result: dict[str, Any]) -> dict[str, Any]:
        articles = result.get("articles", [])
        if not isinstance(articles, list):
            articles = []

        valid_articles = []
        counts = {
            "positive": 0,
            "negative": 0,
            "neutral": 0,
        }

        for article in articles:
            if not isinstance(article, dict):
                continue

            sentiment = str(article.get("sentiment", "")).lower()
            if sentiment not in counts:
                continue

            counts[sentiment] += 1
            valid_articles.append(article)

        total = len(valid_articles)

        positive_ratio = (
            round(counts["positive"] / total * 100, 1)
            if total else 0.0
        )
        negative_ratio = (
            round(counts["negative"] / total * 100, 1)
            if total else 0.0
        )
        neutral_ratio = (
            round(100.0 - positive_ratio - negative_ratio, 1)
            if total else 0.0
        )

        result.update({
            "total_count": total,
            "positive_count": counts["positive"],
            "negative_count": counts["negative"],
            "neutral_count": counts["neutral"],
            "positive_ratio": positive_ratio,
            "negative_ratio": negative_ratio,
            "neutral_ratio": neutral_ratio,
            "sentiment_score": round(
                (
                    counts["positive"] - counts["negative"]
                ) / total * 100,
                1,
            ) if total else 0.0,
            "articles": valid_articles,
        })

        return result
