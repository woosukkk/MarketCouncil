from typing import Any

from tools.source_collector import SourceCollector


class SentimentAgent:
    def __init__(self) -> None:
        self.source_collector = SourceCollector()

    def analyze(
        self,
        company_name: str,
        source_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = source_data or self.source_collector.collect(company_name)
        return self._normalize(result.copy())

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
