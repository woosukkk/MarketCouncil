from typing import Any, Literal, TypedDict

from agents.analysis_axes import AnalysisAxis, axes_by_id


Availability = Literal["available", "unavailable"]
Confidence = Literal["high", "medium", "low"]


class AxisResult(TypedDict):
    axis_id: str
    status: Availability
    direction: int
    summary: str
    verified_facts: list[str]
    market_expectations: list[str]
    analyst_hypotheses: list[str]
    evidence_refs: list[str]
    confidence: Confidence
    counter_conditions: list[str]
    unavailable_reason: str


class PerspectiveAnalysis(TypedDict):
    role: str
    axis_results: list[AxisResult]


PERSPECTIVE_ANALYSIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "role": {"type": "string", "enum": ["bull", "bear"]},
        "axis_results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "axis_id": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["available", "unavailable"],
                    },
                    "direction": {
                        "type": "integer",
                        "enum": [-2, -1, 0, 1, 2],
                    },
                    "summary": {"type": "string"},
                    "verified_facts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": 4,
                    },
                    "market_expectations": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": 3,
                    },
                    "analyst_hypotheses": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": 3,
                    },
                    "evidence_refs": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": 6,
                    },
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                    },
                    "counter_conditions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": 3,
                    },
                    "unavailable_reason": {"type": "string"},
                },
                "required": [
                    "axis_id",
                    "status",
                    "direction",
                    "summary",
                    "verified_facts",
                    "market_expectations",
                    "analyst_hypotheses",
                    "evidence_refs",
                    "confidence",
                    "counter_conditions",
                    "unavailable_reason",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["role", "axis_results"],
    "additionalProperties": False,
}


def normalize_perspective_analysis(
    result: dict[str, Any],
    role: Literal["bull", "bear"],
    axes: list[AnalysisAxis],
    allowed_evidence_ids: set[str] | None = None,
) -> PerspectiveAnalysis:
    definitions = axes_by_id(axes)
    normalized_by_id: dict[str, AxisResult] = {}
    raw_results = result.get("axis_results", [])
    if not isinstance(raw_results, list):
        raw_results = []
    for raw in raw_results:
        if not isinstance(raw, dict):
            continue
        axis_id = str(raw.get("axis_id", ""))
        if axis_id not in definitions or axis_id in normalized_by_id:
            continue
        status: Availability = (
            "available" if raw.get("status") == "available" else "unavailable"
        )
        direction = _integer(raw.get("direction"), 0)
        direction = max(0, direction) if role == "bull" else min(0, direction)
        if status == "unavailable":
            direction = 0
        evidence_refs = _text_list(raw.get("evidence_refs"), 6)
        if allowed_evidence_ids:
            evidence_refs = [
                reference
                for reference in evidence_refs
                if reference in allowed_evidence_ids
            ]
        missing_valid_evidence = (
            status == "available" and bool(allowed_evidence_ids) and not evidence_refs
        )
        if missing_valid_evidence:
            status = "unavailable"
            direction = 0
        normalized_by_id[axis_id] = {
            "axis_id": axis_id,
            "status": status,
            "direction": min(max(direction, -2), 2),
            "summary": _text(raw.get("summary")),
            "verified_facts": _text_list(raw.get("verified_facts"), 4),
            "market_expectations": _text_list(raw.get("market_expectations"), 3),
            "analyst_hypotheses": _text_list(raw.get("analyst_hypotheses"), 3),
            "evidence_refs": evidence_refs,
            "confidence": _confidence(raw.get("confidence")),
            "counter_conditions": _text_list(raw.get("counter_conditions"), 3),
            "unavailable_reason": (
                "유효한 근거 ID가 없어 확인 불가"
                if missing_valid_evidence
                else _text(raw.get("unavailable_reason"))
            ),
        }
    for axis in axes:
        if axis["id"] not in normalized_by_id:
            normalized_by_id[axis["id"]] = unavailable_axis_result(axis["id"])
    return {
        "role": role,
        "axis_results": [normalized_by_id[axis["id"]] for axis in axes],
    }


def unavailable_axis_result(axis_id: str) -> AxisResult:
    return {
        "axis_id": axis_id,
        "status": "unavailable",
        "direction": 0,
        "summary": "확인 불가",
        "verified_facts": [],
        "market_expectations": [],
        "analyst_hypotheses": [],
        "evidence_refs": [],
        "confidence": "low",
        "counter_conditions": [],
        "unavailable_reason": "추가 데이터 필요",
    }


def perspective_to_text(
    analysis: PerspectiveAnalysis,
    axes: list[AnalysisAxis],
) -> str:
    definitions = axes_by_id(axes)
    lines = [f"# {analysis['role'].capitalize()} 축별 분석"]
    for result in analysis["axis_results"]:
        axis = definitions[result["axis_id"]]
        lines.extend(["", f"## {axis['label']}"])
        if result["status"] == "unavailable":
            lines.append(f"- 확인 불가: {result['unavailable_reason'] or '추가 데이터 필요'}")
            continue
        lines.extend([
            f"- 방향: {result['direction']}",
            f"- 요약: {result['summary']}",
            f"- 신뢰도: {result['confidence']}",
        ])
        _append_items(lines, "확인된 사실", result["verified_facts"])
        _append_items(lines, "시장 기대", result["market_expectations"])
        _append_items(lines, "투자 가설", result["analyst_hypotheses"])
        _append_items(lines, "근거 참조", result["evidence_refs"])
        _append_items(lines, "반증 조건", result["counter_conditions"])
    return "\n".join(lines)


def _append_items(lines: list[str], label: str, items: list[str]) -> None:
    if items:
        lines.append(f"- {label}: " + " / ".join(items))


def _text(value: Any) -> str:
    return str(value or "").strip()


def _text_list(value: Any, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := _text(item))][:limit]


def _confidence(value: Any) -> Confidence:
    text = _text(value).lower()
    return text if text in {"high", "medium", "low"} else "low"  # type: ignore[return-value]


def _integer(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
