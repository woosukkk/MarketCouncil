from datetime import date, datetime
from typing import Any, TypedDict


class EmotionAxisDefinition(TypedDict):
    id: str
    label: str
    negative_label: str
    positive_label: str


EMOTION_AXES: tuple[EmotionAxisDefinition, ...] = (
    {
        "id": "expectation",
        "label": "기대",
        "negative_label": "비관",
        "positive_label": "낙관",
    },
    {
        "id": "risk_emotion",
        "label": "위험 정서",
        "negative_label": "공포",
        "positive_label": "안도",
    },
    {
        "id": "certainty",
        "label": "확신",
        "negative_label": "불확실",
        "positive_label": "확신",
    },
    {
        "id": "expectation_gap",
        "label": "기대 차이",
        "negative_label": "실망",
        "positive_label": "긍정적 놀라움",
    },
)

EMOTION_ACTORS = {
    "investor",
    "consumer",
    "management",
    "analyst",
    "policy",
    "mixed",
    "unknown",
}


def normalize_article_emotions(article: dict[str, Any]) -> dict[str, Any]:
    actor = str(article.get("emotion_actor", "unknown")).lower()
    article["emotion_actor"] = actor if actor in EMOTION_ACTORS else "unknown"
    article["emotion_intensity"] = _unit_score(article.get("emotion_intensity"))
    article["emotion_confidence"] = _unit_score(article.get("emotion_confidence"))
    article["event_importance"] = _unit_score(article.get("event_importance"))
    raw_axes = article.get("emotion_axes", {})
    if not isinstance(raw_axes, dict):
        raw_axes = {}
    normalized_axes = {}
    for definition in EMOTION_AXES:
        raw = raw_axes.get(definition["id"], {})
        if not isinstance(raw, dict):
            raw = {}
        status = "available" if raw.get("status") == "available" else "unavailable"
        score = _axis_score(raw.get("score")) if status == "available" else 0
        normalized_axes[definition["id"]] = {
            "status": status,
            "score": score,
            "reason": str(raw.get("reason", "")).strip(),
        }
    article["emotion_axes"] = normalized_axes
    return article


def aggregate_emotion_axes(
    articles: list[dict[str, Any]],
    today: date | None = None,
) -> dict[str, Any]:
    reference_date = today or date.today()
    axis_results = []
    for definition in EMOTION_AXES:
        weighted_score = 0.0
        total_weight = 0.0
        evidence_count = 0
        for article in articles:
            axis = article.get("emotion_axes", {}).get(definition["id"], {})
            if axis.get("status") != "available":
                continue
            weight = _article_weight(article, reference_date)
            if weight <= 0:
                continue
            weighted_score += float(axis.get("score", 0)) * weight
            total_weight += weight
            evidence_count += 1
        if not total_weight:
            axis_results.append({
                "axis_id": definition["id"],
                "label": definition["label"],
                "status": "unavailable",
                "score": 0.0,
                "evidence_count": 0,
                "confidence": "low",
            })
            continue
        score = round(weighted_score / total_weight, 2)
        coverage = evidence_count / len(articles) if articles else 0.0
        axis_results.append({
            "axis_id": definition["id"],
            "label": definition["label"],
            "status": "available",
            "score": score,
            "evidence_count": evidence_count,
            "confidence": _aggregate_confidence(total_weight, coverage),
        })
    actors: dict[str, int] = {}
    for article in articles:
        actor = str(article.get("emotion_actor", "unknown"))
        actors[actor] = actors.get(actor, 0) + 1
    return {
        "scale": {"minimum": -2, "maximum": 2},
        "axes": axis_results,
        "actor_distribution": actors,
        "method": (
            "출처 신뢰도 × 감정 강도 × 분류 신뢰도 × 사건 중요도 × 최신성"
        ),
    }


def _article_weight(article: dict[str, Any], today: date) -> float:
    credibility = _unit_score(article.get("credibility_score"))
    intensity = _unit_score(article.get("emotion_intensity"))
    confidence = _unit_score(article.get("emotion_confidence"))
    importance = _unit_score(article.get("event_importance"))
    freshness = _freshness_weight(article.get("published_date"), today)
    return credibility * intensity * confidence * importance * freshness


def _freshness_weight(value: Any, today: date) -> float:
    text = str(value or "").strip()[:10]
    try:
        published = datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return 0.5
    age = max((today - published).days, 0)
    if age <= 30:
        return 1.0
    if age <= 90:
        return 0.7
    return 0.4


def _aggregate_confidence(total_weight: float, coverage: float) -> str:
    if total_weight >= 2.5 and coverage >= 0.6:
        return "high"
    if total_weight >= 0.8 and coverage >= 0.3:
        return "medium"
    return "low"


def _unit_score(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return round(min(max(score, 0.0), 1.0), 3)


def _axis_score(value: Any) -> int:
    try:
        score = int(value)
    except (TypeError, ValueError):
        return 0
    return min(max(score, -2), 2)
