from typing import Any


CONFIDENCE_UNCERTAINTY = {"high": 0.4, "medium": 0.7, "low": 1.0}
ACTIVE_STATUSES = {"OPEN", "CONTESTED"}
FINAL_STATUSES = {"RESOLVED", "STALEMATE", "UNKNOWN", "INVALID"}
ALL_STATUSES = ACTIVE_STATUSES | FINAL_STATUSES


def select_debate_candidates(
    axes: list[dict[str, Any]],
    bull_analysis: dict[str, Any],
    bear_analysis: dict[str, Any],
    limit: int = 3,
) -> list[dict[str, Any]]:
    definitions = {
        str(axis.get("id")): axis
        for axis in axes
        if isinstance(axis, dict) and axis.get("id")
    }
    bull_by_axis = _results_by_axis(bull_analysis)
    bear_by_axis = _results_by_axis(bear_analysis)
    candidates = []
    for axis_id, definition in definitions.items():
        bull = bull_by_axis.get(axis_id)
        bear = bear_by_axis.get(axis_id)
        if not bull or not bear:
            continue
        if bull.get("status") != "available" or bear.get("status") != "available":
            continue
        bull_evidence = _text_set(bull.get("evidence_refs"))
        bear_evidence = _text_set(bear.get("evidence_refs"))
        if not bull_evidence or not bear_evidence:
            continue
        bull_direction = _integer(bull.get("direction"))
        bear_direction = _integer(bear.get("direction"))
        direction_gap = abs(bull_direction - bear_direction)
        if direction_gap < 2:
            continue
        uncertainty = max(
            CONFIDENCE_UNCERTAINTY.get(str(bull.get("confidence", "low")), 1.0),
            CONFIDENCE_UNCERTAINTY.get(str(bear.get("confidence", "low")), 1.0),
        )
        weight = float(definition.get("weight", 0.0))
        evidence_conflict = 1.0
        priority = round(direction_gap / 4 * weight * evidence_conflict * uncertainty, 6)
        candidates.append({
            "axis_id": axis_id,
            "label": str(definition.get("label", axis_id)),
            "priority": priority,
            "axis_weight": weight,
            "direction_gap": direction_gap,
            "bull_direction": bull_direction,
            "bear_direction": bear_direction,
            "bull_claim": str(bull.get("summary", "")),
            "bear_claim": str(bear.get("summary", "")),
            "bull_evidence_ids": sorted(bull_evidence),
            "bear_evidence_ids": sorted(bear_evidence),
            "allowed_evidence_ids": sorted(bull_evidence | bear_evidence),
        })
    return sorted(
        candidates,
        key=lambda item: (item["priority"], item["axis_weight"]),
        reverse=True,
    )[: max(min(limit, 3), 0)]


def normalize_agenda(
    agenda: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates_by_axis = {item["axis_id"]: item for item in candidates}
    normalized = []
    seen_axes: set[str] = set()
    for raw in agenda:
        if not isinstance(raw, dict):
            continue
        axis_id = str(raw.get("axis_id", ""))
        candidate = candidates_by_axis.get(axis_id)
        if not candidate or axis_id in seen_axes:
            continue
        normalized.append({
            "issue_id": str(raw.get("issue_id", "")).strip() or f"{axis_id}-1",
            "axis_id": axis_id,
            "title": str(raw.get("title", "")).strip() or candidate["label"],
            "bull_claim": str(raw.get("bull_claim", "")).strip() or candidate["bull_claim"],
            "bear_claim": str(raw.get("bear_claim", "")).strip() or candidate["bear_claim"],
            "question": str(raw.get("question", "")).strip()
            or f"{candidate['label']}에 대한 상반된 근거 중 무엇이 더 유효한가?",
            "allowed_evidence_ids": candidate["allowed_evidence_ids"],
        })
        seen_axes.add(axis_id)
    for candidate in candidates:
        if candidate["axis_id"] in seen_axes:
            continue
        normalized.append({
            "issue_id": f"{candidate['axis_id']}-1",
            "axis_id": candidate["axis_id"],
            "title": candidate["label"],
            "bull_claim": candidate["bull_claim"],
            "bear_claim": candidate["bear_claim"],
            "question": f"{candidate['label']}에 대한 상반된 근거 중 무엇이 더 유효한가?",
            "allowed_evidence_ids": candidate["allowed_evidence_ids"],
        })
        if len(normalized) >= 3:
            break
    return normalized[:3]


def validate_participant_response(
    response: dict[str, Any],
    agenda: list[dict[str, Any]],
    evidence_catalog: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    allowed_by_issue = {
        str(issue.get("issue_id")): _text_set(issue.get("allowed_evidence_ids"))
        for issue in agenda
    }
    axis_by_issue = {
        str(issue.get("issue_id")): str(issue.get("axis_id", ""))
        for issue in agenda
    }
    emotion_evidence_ids = {
        str(item.get("id"))
        for item in evidence_catalog or []
        if isinstance(item, dict) and item.get("emotion_available")
    }
    normalized_issues = []
    for issue in response.get("issues", []):
        if not isinstance(issue, dict):
            continue
        issue_id = str(issue.get("issue_id", ""))
        if issue_id not in allowed_by_issue:
            continue
        allowed = allowed_by_issue[issue_id]
        fact_ids = _text_set(issue.get("fact_evidence_ids"))
        emotion_ids = _text_set(issue.get("emotion_evidence_ids"))
        invalid_emotion_ids = (
            emotion_ids - emotion_evidence_ids if evidence_catalog is not None else set()
        )
        target_evidence_id = str(issue.get("target_evidence_id", "")).strip()
        target_ids = {target_evidence_id} if target_evidence_id else set()
        invalid = sorted(
            ((fact_ids | emotion_ids | target_ids) - allowed) | invalid_emotion_ids
        )
        valid_fact = sorted(fact_ids & allowed)
        valid_emotion = sorted(
            (emotion_ids & allowed) - invalid_emotion_ids
        )
        normalized_issues.append({
            **issue,
            "axis_id": axis_by_issue[issue_id],
            "fact_evidence_ids": valid_fact,
            "emotion_evidence_ids": valid_emotion,
            "target_evidence_id": (
                target_evidence_id if target_evidence_id in allowed else ""
            ),
            "invalid_evidence_ids": invalid,
            "evidence": sorted(set(valid_fact + valid_emotion)),
        })
    return {
        "position_summary": str(response.get("position_summary", "")),
        "issues": normalized_issues,
    }


def should_continue_debate(
    review: dict[str, Any],
    current_round: int,
    max_rounds: int,
) -> bool:
    if current_round >= max_rounds or not review.get("continue_debate", False):
        return False
    statuses = {
        str(item.get("status", ""))
        for item in review.get("issue_reviews", [])
        if isinstance(item, dict)
    }
    if not statuses or statuses.issubset(FINAL_STATUSES):
        return False
    if review.get("repeated_claims") and not review.get("new_evidence_ids"):
        return False
    return bool(statuses & ACTIVE_STATUSES)


def normalize_moderator_review(
    review: dict[str, Any],
    agenda: list[dict[str, Any]],
    bull_response: dict[str, Any],
    bear_response: dict[str, Any],
) -> dict[str, Any]:
    agenda_by_issue = {
        str(item.get("issue_id")): item for item in agenda if isinstance(item, dict)
    }
    invalid_by_issue = _invalid_evidence_by_issue(bull_response) | _invalid_evidence_by_issue(
        bear_response
    )
    normalized_reviews = []
    for raw in review.get("issue_reviews", []):
        if not isinstance(raw, dict):
            continue
        issue_id = str(raw.get("issue_id", ""))
        agenda_item = agenda_by_issue.get(issue_id)
        if not agenda_item:
            continue
        status = str(raw.get("status", "UNKNOWN"))
        if status not in ALL_STATUSES:
            status = "UNKNOWN"
        if issue_id in invalid_by_issue:
            status = "INVALID"
        normalized_reviews.append({
            "issue_id": issue_id,
            "axis_id": agenda_item.get("axis_id", ""),
            "status": status,
            "assessment": str(raw.get("assessment", "")),
            "question_for_bull": str(raw.get("question_for_bull", "")),
            "question_for_bear": str(raw.get("question_for_bear", "")),
            "verified_points": _text_list(raw.get("verified_points")),
            "rejected_points": _text_list(raw.get("rejected_points")),
            "remaining_uncertainty": str(raw.get("remaining_uncertainty", "")),
            "confidence_change": _clamp_float(raw.get("confidence_change"), -1.0, 1.0),
        })
    reviewed_ids = {item["issue_id"] for item in normalized_reviews}
    for issue_id, agenda_item in agenda_by_issue.items():
        if issue_id in reviewed_ids:
            continue
        normalized_reviews.append({
            "issue_id": issue_id,
            "axis_id": agenda_item.get("axis_id", ""),
            "status": "UNKNOWN",
            "assessment": "중재 결과 확인 불가",
            "question_for_bull": "",
            "question_for_bear": "",
            "verified_points": [],
            "rejected_points": [],
            "remaining_uncertainty": "추가 데이터 필요",
            "confidence_change": 0.0,
        })
    allowed = {
        evidence_id
        for item in agenda
        for evidence_id in _text_set(item.get("allowed_evidence_ids"))
    }
    new_evidence_ids = sorted(_text_set(review.get("new_evidence_ids")) & allowed)
    return {
        "issue_reviews": normalized_reviews,
        "repeated_claims": _text_list(review.get("repeated_claims")),
        "missing_evidence": _text_list(review.get("missing_evidence")),
        "new_evidence_ids": new_evidence_ids,
        "continue_debate": bool(review.get("continue_debate")),
        "reason": str(review.get("reason", "")),
    }


def normalize_debate_summary(
    summary: dict[str, Any],
    agenda: list[dict[str, Any]],
    final_reviews: list[dict[str, Any]],
) -> dict[str, Any]:
    allowed_axes = {
        str(item.get("axis_id")) for item in agenda if item.get("axis_id")
    }
    review_by_axis = {
        str(item.get("axis_id")): item
        for item in final_reviews
        if isinstance(item, dict) and item.get("axis_id")
    }
    axis_results = []
    seen: set[str] = set()
    for raw in summary.get("axis_debate_results", []):
        if not isinstance(raw, dict):
            continue
        axis_id = str(raw.get("axis_id", ""))
        if axis_id not in allowed_axes or axis_id in seen:
            continue
        review = review_by_axis.get(axis_id, {})
        status = str(review.get("status", raw.get("status", "UNKNOWN")))
        if status not in ALL_STATUSES:
            status = "UNKNOWN"
        axis_results.append({
            "axis_id": axis_id,
            "status": status,
            "verified_points": _text_list(raw.get("verified_points")),
            "rejected_points": _text_list(raw.get("rejected_points")),
            "remaining_hypotheses": _text_list(raw.get("remaining_hypotheses")),
            "required_evidence": _text_list(raw.get("required_evidence")),
            "confidence_change": _clamp_float(
                raw.get("confidence_change", review.get("confidence_change", 0.0)),
                -1.0,
                1.0,
            ),
        })
        seen.add(axis_id)
    for axis_id in allowed_axes - seen:
        review = review_by_axis.get(axis_id, {})
        axis_results.append({
            "axis_id": axis_id,
            "status": str(review.get("status", "UNKNOWN")),
            "verified_points": _text_list(review.get("verified_points")),
            "rejected_points": _text_list(review.get("rejected_points")),
            "remaining_hypotheses": [],
            "required_evidence": [],
            "confidence_change": _clamp_float(
                review.get("confidence_change", 0.0), -1.0, 1.0
            ),
        })
    return {
        "agreements": _text_list(summary.get("agreements")),
        "unresolved_issues": _text_list(summary.get("unresolved_issues")),
        "required_evidence": _text_list(summary.get("required_evidence")),
        "axis_debate_results": axis_results,
        "summary": str(summary.get("summary", "")),
    }


def _results_by_axis(analysis: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("axis_id")): item
        for item in analysis.get("axis_results", [])
        if isinstance(item, dict) and item.get("axis_id")
    }


def _text_set(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {str(item).strip() for item in value if str(item).strip()}


def _text_list(value: Any) -> list[str]:
    return sorted(_text_set(value))


def _invalid_evidence_by_issue(response: dict[str, Any]) -> set[str]:
    return {
        str(item.get("issue_id"))
        for item in response.get("issues", [])
        if isinstance(item, dict) and item.get("invalid_evidence_ids")
    }


def _clamp_float(value: Any, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return round(min(max(number, minimum), maximum), 3)


def _integer(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
