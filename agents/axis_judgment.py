from typing import Any, TypedDict

from agents.analysis_axes import AnalysisAxis, axes_by_id


class AxisJudgment(TypedDict):
    axis_id: str
    status: str
    verdict: int
    confidence: str
    reason: str
    bull_evidence_refs: list[str]
    bear_evidence_refs: list[str]
    strengthening_conditions: list[str]
    weakening_conditions: list[str]
    invalidation_conditions: list[str]


AXIS_JUDGMENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "axis_judgments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "axis_id": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["available", "unavailable"],
                    },
                    "verdict": {
                        "type": "integer",
                        "enum": [-2, -1, 0, 1, 2],
                    },
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                    },
                    "reason": {"type": "string"},
                    "bull_evidence_refs": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": 6,
                    },
                    "bear_evidence_refs": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": 6,
                    },
                    "strengthening_conditions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": 3,
                    },
                    "weakening_conditions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": 3,
                    },
                    "invalidation_conditions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": 3,
                    },
                },
                "required": [
                    "axis_id",
                    "status",
                    "verdict",
                    "confidence",
                    "reason",
                    "bull_evidence_refs",
                    "bear_evidence_refs",
                    "strengthening_conditions",
                    "weakening_conditions",
                    "invalidation_conditions",
                ],
                "additionalProperties": False,
            },
        },
        "evidence_limitations": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 5,
        },
        "conditional_conclusion": {"type": "string"},
    },
    "required": [
        "axis_judgments",
        "evidence_limitations",
        "conditional_conclusion",
    ],
    "additionalProperties": False,
}


def normalize_axis_judgment(
    result: dict[str, Any],
    axes: list[AnalysisAxis],
    allowed_evidence_ids: set[str] | None = None,
    available_axis_ids: set[str] | None = None,
) -> dict[str, Any]:
    definitions = axes_by_id(axes)
    normalized: dict[str, AxisJudgment] = {}
    raw_judgments = result.get("axis_judgments", [])
    if not isinstance(raw_judgments, list):
        raw_judgments = []
    for raw in raw_judgments:
        if not isinstance(raw, dict):
            continue
        axis_id = str(raw.get("axis_id", ""))
        if axis_id not in definitions or axis_id in normalized:
            continue
        status = "available" if raw.get("status") == "available" else "unavailable"
        if available_axis_ids is not None and axis_id not in available_axis_ids:
            status = "unavailable"
        verdict = _integer(raw.get("verdict"))
        if status == "unavailable":
            verdict = 0
        bull_refs = _text_list(raw.get("bull_evidence_refs"))
        bear_refs = _text_list(raw.get("bear_evidence_refs"))
        if allowed_evidence_ids:
            bull_refs = [ref for ref in bull_refs if ref in allowed_evidence_ids]
            bear_refs = [ref for ref in bear_refs if ref in allowed_evidence_ids]
        normalized[axis_id] = {
            "axis_id": axis_id,
            "status": status,
            "verdict": min(max(verdict, -2), 2),
            "confidence": _confidence(raw.get("confidence")),
            "reason": _text(raw.get("reason")) or "확인 불가",
            "bull_evidence_refs": bull_refs,
            "bear_evidence_refs": bear_refs,
            "strengthening_conditions": _text_list(raw.get("strengthening_conditions"), 3),
            "weakening_conditions": _text_list(raw.get("weakening_conditions"), 3),
            "invalidation_conditions": _text_list(raw.get("invalidation_conditions"), 3),
        }
    for axis in axes:
        normalized.setdefault(axis["id"], _unavailable_judgment(axis["id"]))
    judgments = [normalized[axis["id"]] for axis in axes]
    aggregate = aggregate_axis_judgments(judgments, axes)
    return {
        "schema_version": "1.0",
        "axis_judgments": judgments,
        "overall": aggregate,
        "evidence_limitations": _text_list(result.get("evidence_limitations"), 5),
        "conditional_conclusion": _text(result.get("conditional_conclusion")),
    }


def aggregate_axis_judgments(
    judgments: list[AxisJudgment],
    axes: list[AnalysisAxis],
) -> dict[str, Any]:
    definitions = axes_by_id(axes)
    available = [item for item in judgments if item["status"] == "available"]
    available_weight = sum(definitions[item["axis_id"]]["weight"] for item in available)
    weighted = sum(
        item["verdict"] * definitions[item["axis_id"]]["weight"]
        for item in available
    )
    coverage = round(available_weight, 3)
    bull_score = round((weighted + 2) / 4 * 100)
    bull_score = min(max(bull_score, 0), 100)
    confidence_points = {"low": 1, "medium": 2, "high": 3}
    confidence_average = (
        sum(confidence_points[item["confidence"]] for item in available) / len(available)
        if available
        else 0
    )
    if coverage < 0.5 or confidence_average < 1.5:
        confidence = "Low"
    elif coverage >= 0.8 and confidence_average >= 2.5:
        confidence = "High"
    else:
        confidence = "Medium"
    return {
        "weighted_score": round(weighted, 3),
        "rating": _rating(weighted, coverage),
        "bull_score": bull_score,
        "bear_score": 100 - bull_score,
        "confidence": confidence,
        "evidence_coverage": coverage,
    }


def judgment_to_text(result: dict[str, Any], axes: list[AnalysisAxis]) -> str:
    definitions = axes_by_id(axes)
    overall = result.get("overall", {})
    lines = ["# 핵심 결론"]
    conclusion = str(result.get("conditional_conclusion", "")).strip()
    lines.append(conclusion or "현재 증거만으로 단정적인 결론을 내리기 어렵다.")
    lines.extend(["", "# 축별 판단"])
    for item in result.get("axis_judgments", []):
        axis = definitions.get(item.get("axis_id"))
        if not axis:
            continue
        if item.get("status") == "unavailable":
            lines.append(f"- {axis['label']}: 확인 불가 — 추가 데이터 필요")
        else:
            lines.append(
                f"- {axis['label']}: {item.get('verdict', 0):+d} "
                f"({item.get('confidence', 'low')}) — {item.get('reason', '')}"
            )
    limitations = result.get("evidence_limitations", [])
    lines.extend(["", "# 추가 확인 데이터"])
    lines.extend(f"- {item}" for item in limitations)
    if not limitations:
        lines.append("- 추가 데이터 필요")
    strengthening = [
        condition
        for item in result.get("axis_judgments", [])
        for condition in item.get("strengthening_conditions", [])
    ]
    weakening = [
        condition
        for item in result.get("axis_judgments", [])
        for condition in (
            item.get("weakening_conditions", [])
            + item.get("invalidation_conditions", [])
        )
    ]
    lines.extend(["", "# 가설 강화 조건"])
    lines.extend(f"- {item}" for item in dict.fromkeys(strengthening))
    if not strengthening:
        lines.append("- 확인 불가")
    lines.extend(["", "# 가설 약화·폐기 조건"])
    lines.extend(f"- {item}" for item in dict.fromkeys(weakening))
    if not weakening:
        lines.append("- 확인 불가")
    lines.extend([
        "",
        "# 최종 판단",
        f"- Final Rating: {overall.get('rating', 'Neutral')}",
        f"- Bull Score: {overall.get('bull_score', 50)}",
        f"- Bear Score: {overall.get('bear_score', 50)}",
        f"- Confidence: {overall.get('confidence', 'Low')}",
        f"- Evidence Coverage: {overall.get('evidence_coverage', 0):.1%}",
        f"- 조건부 판단: {conclusion or '추가 데이터가 확보될 때 재평가'}",
    ])
    return "\n".join(lines)


def compare_axis_judgments(
    current: dict[str, Any],
    previous: dict[str, Any] | None,
    axes: list[AnalysisAxis],
) -> list[dict[str, Any]]:
    if not previous:
        return []
    definitions = axes_by_id(axes)
    old = {
        item.get("axis_id"): item
        for item in previous.get("axis_judgments", [])
        if isinstance(item, dict)
    }
    changes = []
    for item in current.get("axis_judgments", []):
        axis_id = item.get("axis_id")
        prior = old.get(axis_id)
        if not prior or axis_id not in definitions:
            continue
        if prior.get("verdict") == item.get("verdict") and prior.get("status") == item.get("status"):
            continue
        changes.append({
            "axis_id": axis_id,
            "label": definitions[axis_id]["label"],
            "previous_status": prior.get("status", "unavailable"),
            "previous_verdict": prior.get("verdict", 0),
            "current_status": item.get("status", "unavailable"),
            "current_verdict": item.get("verdict", 0),
        })
    return changes


def _rating(score: float, coverage: float) -> str:
    if coverage < 0.35:
        return "Neutral"
    if score >= 1.2:
        return "Strong Bull"
    if score >= 0.4:
        return "Bull"
    if score <= -1.2:
        return "Strong Bear"
    if score <= -0.4:
        return "Bear"
    return "Neutral"


def _unavailable_judgment(axis_id: str) -> AxisJudgment:
    return {
        "axis_id": axis_id,
        "status": "unavailable",
        "verdict": 0,
        "confidence": "low",
        "reason": "확인 불가",
        "bull_evidence_refs": [],
        "bear_evidence_refs": [],
        "strengthening_conditions": [],
        "weakening_conditions": [],
        "invalidation_conditions": [],
    }


def _text(value: Any) -> str:
    return str(value or "").strip()


def _text_list(value: Any, limit: int = 6) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := _text(item))][:limit]


def _confidence(value: Any) -> str:
    value = _text(value).lower()
    return value if value in {"high", "medium", "low"} else "low"


def _integer(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
