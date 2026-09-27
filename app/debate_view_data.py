import json
from pathlib import Path
from typing import Any


def list_debate_files(
    base_dir: Path = Path("results/analysis_debate"),
) -> list[Path]:
    if not base_dir.exists():
        return []
    return sorted(
        base_dir.rglob("analysis_debate_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def load_debate(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"토론 파일을 읽을 수 없습니다: {path}") from error
    if not isinstance(data, dict):
        raise ValueError("토론 결과는 JSON 객체여야 합니다.")
    return data


def find_issue_turn(
    response: dict[str, Any],
    issue_id: str,
) -> dict[str, Any]:
    return next(
        (
            issue for issue in response.get("issues", [])
            if str(issue.get("issue_id", "")) == issue_id
        ),
        {},
    )


def collect_evidence(debate: dict[str, Any]) -> dict[str, dict[str, Any]]:
    evidence: dict[str, dict[str, Any]] = {}
    legacy_number = 0
    for round_data in debate.get("rounds", []):
        for side in ("bull_response", "bear_response"):
            for issue in round_data.get(side, {}).get("issues", []):
                for item in issue.get("evidence", []):
                    if not isinstance(item, dict):
                        legacy_number += 1
                        evidence[f"LEGACY-{legacy_number:03d}"] = {
                            "evidence_id": f"LEGACY-{legacy_number:03d}",
                            "reason": str(item),
                            "verified": False,
                        }
                        continue
                    evidence_id = str(item.get("evidence_id", "")).strip()
                    if not evidence_id:
                        legacy_number += 1
                        evidence_id = f"LEGACY-{legacy_number:03d}"
                    evidence.setdefault(evidence_id, {**item, "evidence_id": evidence_id})
    for reasons in debate.get("regime_analysis", {}).get("reasons", {}).values():
        for reason in reasons:
            for item in reason.get("evidence", []):
                if not isinstance(item, dict):
                    continue
                evidence_id = str(item.get("evidence_id", "")).strip()
                if evidence_id:
                    evidence.setdefault(evidence_id, item)
    for periods in debate.get("regime_analysis", {}).get("timeline_evidence", {}).values():
        for items in periods.values():
            for item in items:
                evidence_id = str(item.get("evidence_id", "")).strip()
                if evidence_id:
                    evidence.setdefault(evidence_id, item)
    return evidence


def navigation_issue(debate: dict[str, Any], issue_id: str) -> dict[str, Any]:
    return next(
        (
            item for item in debate.get("navigation", {}).get("issues", [])
            if str(item.get("issue_id", "")) == issue_id
        ),
        {},
    )


def ordered_agenda(debate: dict[str, Any]) -> list[dict[str, Any]]:
    """Ignore unknown/duplicate editorial IDs and retain every original issue."""
    agenda = debate.get("agenda", [])
    by_id = {str(item.get("issue_id", "")): item for item in agenda}
    priority = debate.get("moderator_summary", {}).get("priority_issue_ids", [])
    if not isinstance(priority, list):
        priority = []
    ids = dict.fromkeys(str(value) for value in [*priority, *by_id])
    return [by_id[value] for value in ids if value in by_id]


def issue_status(debate: dict[str, Any], issue_id: str) -> str:
    guide = navigation_issue(debate, issue_id)
    if guide.get("status"):
        return str(guide["status"])
    status = next(
        (
            item.get("status", "UNKNOWN")
            for item in debate.get("issue_statuses", [])
            if str(item.get("issue_id", "")) == issue_id
        ),
        "UNKNOWN",
    )
    return str(status)


def round_change(
    debate: dict[str, Any],
    issue_id: str,
    round_number: int,
) -> dict[str, Any]:
    issue = navigation_issue(debate, issue_id)
    return next(
        (
            item for item in issue.get("round_changes", [])
            if item.get("round") == round_number
        ),
        {},
    )
