"""Offline human-reference evaluation; statements and quotations stay in local queues."""
import argparse
import hashlib
import json
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.citation_quality import assess_issue_evidence
from tools.evidence_dates import parse_evidence_date

LABELS = ("supported", "contradicted", "insufficient_evidence")
ORIGINS = ("human", "model", "unreviewed")
STATEMENTS = ("claim", "response", "warrant", "example_or_data")
WARNINGS = {"invalid_numeric_format", "non_evidentiary_quote", "number_not_in_quotes", "source_date_missing", "future_source", "stale_forecast"}
MAX_CASES = 1000


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _label(origin: Any, label: Any) -> None:
    if origin not in ORIGINS or (label is not None and label not in LABELS) or (origin == "unreviewed" and label is not None):
        raise ValueError("검토 출처와 supported/contradicted/insufficient_evidence 라벨을 확인하세요.")


def _validate_input(value: Any) -> None:
    if not isinstance(value, dict) or value.get("side") not in ("bull", "bear"):
        raise ValueError("로컬 검토 입력 형식을 확인하세요.")
    if any(type(value.get(key)) is not int or not 1 <= value[key] <= MAX_CASES for key in ("round_index", "issue_index")):
        raise ValueError("검토 위치가 올바르지 않습니다.")
    as_of = value.get("as_of_date")
    if as_of is not None and (not isinstance(as_of, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", as_of) or parse_evidence_date(as_of) is None):
        raise ValueError("검토 기준일을 확인하세요.")
    statements = value.get("statements")
    if not isinstance(statements, dict) or any(not isinstance(statements.get(key), str) or len(statements[key]) > 100000 for key in STATEMENTS) or not any(statements[key] for key in STATEMENTS):
        raise ValueError("검토할 발언이 없습니다.")
    evidence = value.get("evidence")
    if not isinstance(evidence, list) or len(evidence) > 100:
        raise ValueError("검토 인용 형식을 확인하세요.")
    for item in evidence:
        if not isinstance(item, dict) or any(not isinstance(item.get(key), str) or len(item[key]) > 100000 for key in ("source_id", "quote_id", "text", "source_url", "published_at")):
            raise ValueError("검토 인용 필드를 확인하세요.")
    checks = value.get("checks")
    if not isinstance(checks, dict) or checks.get("identity_status") not in ("matched", "missing", "invalid") or checks.get("numeric_status") not in ("values_present", "needs_review", "not_applicable"):
        raise ValueError("규칙 진단 필드를 확인하세요.")
    warnings = checks.get("warnings")
    if not isinstance(warnings, list) or any(not isinstance(item, str) or item not in WARNINGS for item in warnings):
        raise ValueError("규칙 경고를 확인하세요.")


def validate_queue(data: dict) -> None:
    if not isinstance(data, dict) or data.get("schema_version") != 1 or data.get("dataset_kind") not in ("real", "synthetic"):
        raise ValueError("실제 사례와 합성 회귀 데이터셋을 명시하세요.")
    cases = data.get("cases")
    if not isinstance(cases, list) or not 1 <= len(cases) <= MAX_CASES:
        raise ValueError("검토 사례가 1~1000개 필요합니다. 빈 템플릿은 평가할 수 없습니다.")
    seen_ids, seen_hashes = set(), set()
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("case_id"), str) or not re.fullmatch(r"C-\d{6}", case["case_id"]):
            raise ValueError("검토 ID는 내보낸 C-000001 형식을 사용하세요.")
        _validate_input(case.get("input"))
        if case.get("input_hash") != _hash(case["input"]) or case["case_id"] in seen_ids or case["input_hash"] in seen_hashes:
            raise ValueError("검토 ID·입력 해시가 중복되거나 입력이 변경됐습니다. 다시 내보내세요.")
        seen_ids.add(case["case_id"]); seen_hashes.add(case["input_hash"])
        review = case.get("review")
        if not isinstance(review, dict):
            raise ValueError("검토 출처와 라벨이 필요합니다.")
        _label(review.get("origin"), review.get("label"))


def export_review_queue(result: dict, dataset_kind: str = "real") -> dict:
    """Export only debate issues and their cited excerpts, never keys or full documents."""
    if not isinstance(result, dict) or not isinstance(result.get("rounds"), list) or not isinstance(result.get("evidence_catalog"), list):
        raise ValueError("rounds와 evidence_catalog가 있는 로컬 분석 원본을 선택하세요.")
    catalog = result["evidence_catalog"]
    if any(not isinstance(row, dict) or not isinstance(row.get("quotes", []), list) or any(not isinstance(quote, dict) for quote in row.get("quotes", [])) for row in catalog):
        raise ValueError("로컬 근거 카탈로그 형식을 확인하세요.")
    by_id = {str(row.get("source_id", "")): row for row in catalog}
    parsed_date = parse_evidence_date(result.get("analysis_as_of"))
    as_of = parsed_date.isoformat() if parsed_date else None
    cases = []
    for round_index, round_data in enumerate(result["rounds"], 1):
        if not isinstance(round_data, dict):
            raise ValueError("토론 라운드 형식을 확인하세요.")
        for side in ("bull", "bear"):
            turn = round_data.get(side + "_response") or {}
            if not isinstance(turn, dict) or not isinstance(turn.get("issues", []), list):
                raise ValueError("토론 발언 형식을 확인하세요.")
            for issue_index, issue in enumerate(turn.get("issues", []), 1):
                if not isinstance(issue, dict) or any(issue.get(key) is not None and not isinstance(issue.get(key), str) for key in STATEMENTS):
                    raise ValueError("토론 쟁점 형식을 확인하세요.")
                checks = assess_issue_evidence(issue, catalog, as_of)
                evidence = []
                for item in issue.get("evidence", []):
                    if not isinstance(item, dict):
                        continue
                    source = by_id.get(str(item.get("source_id", "")), {})
                    quotes = source.get("quotes", [])
                    original = next((quote for quote in quotes if isinstance(quote, dict) and str(quote.get("quote_id", "")) == str(item.get("quote_id", ""))), {})
                    evidence.append({
                        "source_id": str(item.get("source_id", "")), "quote_id": str(item.get("quote_id", "")),
                        "text": str(item.get("exact_quote", original.get("text", ""))),
                        "source_url": str(source.get("source_url", item.get("source_url", ""))),
                        "published_at": str(source.get("published_at", item.get("published_at", ""))),
                    })
                value = {"round_index": round_index, "side": side, "issue_index": issue_index, "as_of_date": as_of,
                         "statements": {key: issue.get(key, "") if isinstance(issue.get(key, ""), str) else "" for key in STATEMENTS},
                         "evidence": evidence, "checks": {key: checks[key] for key in ("identity_status", "numeric_status", "warnings")}}
                cases.append({"case_id": f"C-{len(cases)+1:06d}", "input_hash": _hash(value), "input": value,
                              "review": {"origin": "unreviewed", "label": None}})
    data = {"schema_version": 1, "dataset_kind": dataset_kind, "cases": cases}
    validate_queue(data)
    return data


def evaluate_quality(data: dict, predictions: dict | None = None) -> dict:
    """Score provided human references; model labels never become human gold."""
    started = time.perf_counter()
    validate_queue(data)
    predictions = predictions if predictions is not None else {"schema_version": 1, "origin": "unreviewed", "cases": []}
    if not isinstance(predictions, dict) or predictions.get("schema_version") != 1 or predictions.get("origin") not in ORIGINS or not isinstance(predictions.get("cases"), list) or len(predictions["cases"]) > MAX_CASES:
        raise ValueError("별도 예측 파일의 출처와 사례 목록을 확인하세요.")
    origin = predictions["origin"]
    by_id = {case["case_id"]: case for case in data["cases"]}
    predicted = {}
    for row in predictions["cases"]:
        if not isinstance(row, dict) or not isinstance(row.get("case_id"), str) or row.get("case_id") not in by_id or row["case_id"] in predicted or row.get("input_hash") != by_id[row["case_id"]]["input_hash"]:
            raise ValueError("예측은 검토 사례 ID와 입력 해시에 정확히 대응해야 합니다.")
        _label(origin, row.get("label"))
        predicted[row["case_id"]] = row.get("label")
    confusion = {f"confusion_{gold}_{prediction}": 0 for gold in LABELS for prediction in LABELS}
    reviewed = compared = prediction_count = correct = numeric = identity = future = 0
    rows = []
    origins = set()
    for case in data["cases"]:
        review = case["review"]; origins.add(review["origin"])
        gold = review.get("label"); prediction = predicted.get(case["case_id"])
        is_reviewed = review["origin"] == "human" and gold is not None
        is_compared = is_reviewed and prediction is not None
        reviewed += int(is_reviewed); prediction_count += int(prediction is not None)
        compared += int(is_compared); correct += int(is_compared and gold == prediction)
        if is_compared:
            confusion[f"confusion_{gold}_{prediction}"] += 1
        checks = case["input"]["checks"]
        numeric += int(checks["numeric_status"] == "needs_review")
        identity += int(checks["identity_status"] != "matched")
        future += int("future_source" in checks["warnings"])
        rows.append({"case_id": case["case_id"], "input_hash": case["input_hash"], "gold_origin": review["origin"],
                     "prediction_origin": origin, "gold_label": gold, "prediction_label": prediction,
                     "correct": int(gold == prediction) if is_compared else None,
                     "numeric_review": checks["numeric_status"] == "needs_review",
                     "identity_invalid": checks["identity_status"] != "matched",
                     "future_source": "future_source" in checks["warnings"]})
    count = len(rows)
    return {"schema_version": 1, "kind": "rag", "scope": "answer_quality", "id": str(uuid.uuid4()),
            "recorded_at": datetime.now(timezone.utc).isoformat(), "label": "Claim-evidence support", "version": "1", "status": "success",
            "dataset_hash": _hash(data), "settings": {"case_count": count, "dataset_kind": data["dataset_kind"],
                "annotation_origin": next(iter(origins)) if len(origins) == 1 else "mixed", "prediction_origin": origin,
                "semantic_status": "evaluated" if compared else "not_evaluated", "predictions_hash": _hash(predictions)},
            "metrics": {"duration_ms": (time.perf_counter()-started)*1000, "case_count": count, "reviewed_count": reviewed,
                "compared_count": compared, "prediction_count": prediction_count, "semantic_accuracy": correct/compared if compared else None,
                "review_coverage": reviewed/count, "numeric_review_count": numeric, "identity_invalid_count": identity,
                "future_source_count": future, **confusion}, "cases": rows}


def _read_json(path: Path) -> dict:
    if path.stat().st_size > 20*1024*1024:
        raise ValueError("20MB 이하의 로컬 JSON 파일을 선택하세요.")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("로컬 JSON 객체가 필요합니다.")
    return value


def _write_new(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as output:
        json.dump(value, output, ensure_ascii=False, indent=2, allow_nan=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="로컬 주장-인용 검토 큐 및 사람 정답 비교. API 호출 없음.")
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export")
    export.add_argument("result", type=Path); export.add_argument("--output", type=Path, required=True)
    export.add_argument("--dataset-kind", choices=("real", "synthetic"), default="real")
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("queue", type=Path); evaluate.add_argument("--predictions", type=Path)
    evaluate.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "export":
            value = export_review_queue(_read_json(args.result), args.dataset_kind)
        else:
            value = evaluate_quality(_read_json(args.queue), _read_json(args.predictions) if args.predictions else None)
        _write_new(args.output, value)
    except (OSError, ValueError, TypeError, KeyError):
        parser.error("로컬 입력 형식·입력 해시·검토 라벨 또는 출력 경로를 확인하세요. 기존 파일은 덮어쓰지 않습니다.")
    print("로컬 검토 큐 저장 완료" if args.command == "export" else "원문 없는 품질 평가 보고서 저장 완료")


if __name__ == "__main__":
    main()
