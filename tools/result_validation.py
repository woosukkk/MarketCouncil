"""Validate saved debate fields consumed by the public viewer, without changing data."""
import math
from typing import Any, Callable


def _optional(value: Any, check: Callable[[Any], bool]) -> bool:
    return value is None or check(value)


def _text(value: Any) -> bool:
    return isinstance(value, str)


def _list(value: Any, check: Callable[[Any], bool]) -> bool:
    return isinstance(value, list) and len(value) <= 1000 and all(check(item) for item in value)


def _texts(value: dict[str, Any], keys: tuple[str, ...]) -> bool:
    return all(_optional(value.get(key), _text) for key in keys)


def _scalar(value: Any) -> bool:
    if _text(value):
        return True
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def _text_list(value: Any) -> bool:
    return _list(value, _text)


def _evidence(value: Any) -> bool:
    if value is None or _text(value):
        return True  # Older results stored citations as text.
    return isinstance(value, dict) and _texts(value, (
        "evidence_id", "source_id", "exact_quote", "reason", "title", "source_type",
        "source_url", "published_at", "source_page_url", "context_text",
    )) and _optional(value.get("verified"), lambda item: isinstance(item, bool)) and _optional(value.get("page_number"), _scalar)


def _issue(value: Any) -> bool:
    return isinstance(value, dict) and _texts(value, (
        "issue_id", "title", "question", "bull_claim", "bear_claim", "claim", "warrant",
        "qualifier", "status", "assessment", "core_disagreement",
    )) and _optional(value.get("missing_evidence"), lambda item: _text(item) or _text_list(item)) and _optional(value.get("evidence"), lambda item: _list(item, _evidence))


def _response(value: Any) -> bool:
    return isinstance(value, dict) and _optional(value.get("issues"), lambda item: _list(item, _issue))


def _review(value: Any) -> bool:
    return isinstance(value, dict) and _optional(value.get("issue_reviews"), lambda item: _list(item, _issue))


def _round(value: Any) -> bool:
    return isinstance(value, dict) and _optional(value.get("round"), _scalar) and _optional(value.get("bull_response"), _response) and _optional(value.get("bear_response"), _response) and _optional(value.get("moderator_review"), _review)


def _summary(value: Any) -> bool:
    return isinstance(value, dict) and _texts(value, ("summary", "headline", "lead")) and all(_optional(value.get(key), _text_list) for key in ("agreements", "unresolved_issues", "required_evidence"))


def _navigation(value: Any) -> bool:
    return isinstance(value, dict) and _texts(value, ("overview",)) and _optional(value.get("issues"), lambda item: _list(item, _issue))


def validate_result(value: Any) -> dict[str, Any]:
    """Reject malformed render fields; retain absent/null legacy fields and extra metadata."""
    if (not isinstance(value, dict) or not _text(value.get("company_name"))
        or not value["company_name"].strip() or len(value["company_name"]) > 120
        or not _list(value.get("rounds"), _round)
        or not _texts(value, ("created_at", "bull_analysis", "bear_analysis"))
        or not _optional(value.get("financial_data"), lambda item: isinstance(item, dict) and _texts(item, ("ticker", "price_date")))
        or not _optional(value.get("agenda"), lambda item: _list(item, _issue))
        or not _optional(value.get("issue_statuses"), lambda item: _list(item, _issue))
        or not _optional(value.get("moderator_summary"), _summary)
        or not _optional(value.get("navigation"), _navigation)):
        raise ValueError("분석 결과 형식이 올바르지 않아 열 수 없습니다. 원본 결과를 확인해 주세요.")
    return value
