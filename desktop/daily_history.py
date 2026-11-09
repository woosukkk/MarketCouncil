"""Local daily-run metadata; checkpoints are never treated as publication receipts."""
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

STATUSES = {
    "not_run": "미실행", "checking": "준비 확인 중", "attempting": "분석 중",
    "analysis_failed": "분석 실패", "pending_upload": "게시 대기", "failed": "실패",
    "completed": "공식 게시 완료", "checkpoint": "중간 저장 · 게시 여부 미확인",
}
STAGES = {
    "credentials": "저장된 인증 설정", "account": "계정·공식 게시 권한 확인",
    "evidence": "기업 근거 준비", "services": "Docker·검색 서비스 준비",
    "analysis": "AI 분석", "result": "결과 검증", "publish": "업로드·공식 게시",
    "cleanup": "실행 환경 정리", "cleanup_search": "검색 서비스 종료",
    "cleanup_docker": "Docker 종료",
}


def valid_day(value: object) -> bool:
    try:
        return isinstance(value, str) and date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def read_record(path: Path, warnings: list[str]) -> dict:
    try:
        if path.stat().st_size > 65536:
            raise ValueError("oversize metadata")
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(value, dict):
            raise ValueError("invalid metadata")
        return value
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        warnings.append(path.name + " · 기록을 읽을 수 없습니다.")
        return {}


def state_summary(state: dict) -> dict:
    target = state.get("target")
    company = target.get("company_name", "") if isinstance(target, dict) else state.get("company", "")
    attempts = state.get("analysis_attempts", 0)
    return {
        "day": state.get("day"),
        "status": state.get("status") if isinstance(state.get("status"), str) and state["status"] in STATUSES else "failed",
        "company": company[:120] if isinstance(company, str) else "",
        "analysis_attempts": attempts if type(attempts) is int and 0 <= attempts <= 100 else 0,
        "result_saved": bool(state.get("result_path") or state.get("result_saved")),
    }


def record_run(data: Path, state: dict, stage: str = "") -> None:
    """Best-effort history must never invalidate a saved analysis or publication."""
    if not valid_day(state.get("day")):
        return
    try:
        folder = data / "history"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / (state["day"] + ".json")
        record = {**state_summary(state), "updated_at": datetime.now(timezone.utc).isoformat()}
        record["stage"] = stage if stage in STAGES else ""
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        temporary.replace(path)
    except OSError:
        pass


def is_running(data: Path) -> bool:
    if not (data / "run.lock").exists():
        return False
    import msvcrt
    try:
        with (data / "run.lock").open("r+b") as handle:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return False
    except OSError:
        return True


def load_history(data: Path, day: str, running: bool) -> tuple[list[dict], list[str]]:
    rows: dict[str, dict] = {}
    warnings: list[str] = []
    # shortcut: old publication receipts were not retained locally; keep their status unknown.
    for path in data.glob("analysis-*.json"):
        match = re.fullmatch(r"analysis-(\d{4}-\d{2}-\d{2})(?:-[0-9a-f]+){0,2}\.json", path.name)
        if match and valid_day(match[1]):
            rows.setdefault(match[1], {"day": match[1], "status": "checkpoint"})
    for path in sorted((data / "history").glob("*.json")):
        record = read_record(path, warnings)
        if valid_day(record.get("day")):
            rows[record["day"]] = {**state_summary(record), "stage": record.get("stage", "")}
    state = read_record(data / "state.json", warnings)
    if valid_day(state.get("day")):
        previous = rows.get(state["day"], {})
        # The current state remains authoritative for recovery and publication.
        rows[state["day"]] = {**previous, **state_summary(state)}
        if previous.get("status") == "failed" and state.get("status") != "completed":
            rows[state["day"]]["status"] = "failed"
    paths = sorted((data / "errors").glob("*.json")) + [data / "last-error.json"]
    seen: set[str] = set()
    for path in paths:
        error = read_record(path, warnings)
        if not valid_day(error.get("day")):
            continue
        identity = json.dumps(error, sort_keys=True)
        if identity in seen:
            continue
        seen.add(identity)
        row = rows.setdefault(error["day"], {"day": error["day"], "status": "failed"})
        row.setdefault("errors", []).append(error)
        if row["status"] == "checkpoint" and not str(error.get("stage", "")).startswith("cleanup"):
            row["status"] = "failed"
    rows.setdefault(day, {"day": day, "status": "not_run"})
    active_day = day if rows[day]["status"] == "checking" else state.get("day", day)
    for row in rows.values():
        status = row["status"]
        label = STATUSES[status]
        if status in {"checking", "attempting"} and not running:
            label = "중단됨 · 이어서 실행 가능" if row.get("analysis_attempts", 0) < 2 else "중단됨 · 오늘 시도 한도 도달"
        if row.get("errors") and status == "pending_upload":
            label = "게시 실패 · 결과 보존됨"
        if running and row["day"] == active_day:
            label = "실행 중" if status != "completed" else "게시 완료 · 마무리 중"
        row["label"] = label
    return sorted(rows.values(), key=lambda row: row["day"], reverse=True), warnings


def failure_text(error: dict) -> str:
    stage_key = error.get("stage")
    stage = STAGES.get(stage_key, "단계 미확인") if isinstance(stage_key, str) else "단계 미확인"
    names: list[str] = []
    reasons: list[str] = []
    causes = error.get("causes")
    for cause in ([error] + causes if isinstance(causes, list) else [error]):
        if not isinstance(cause, dict):
            continue
        name = cause.get("type", cause.get("error_type", ""))
        if isinstance(name, str) and re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]{0,80}", name) and name not in names:
            names.append(name)
        code = cause.get("api_code")
        reason = {
            "insufficient_quota": "OpenAI 사용 한도·잔액 부족", "credit_balance_exhausted": "OpenAI 잔액 소진",
            "rate_limit_exceeded": "API 요청 속도 한도 초과", "invalid_api_key": "API 키 인증 실패",
            "context_length_exceeded": "모델 입력 길이 한도 초과",
        }.get(code) if isinstance(code, str) else None
        if reason:
            reasons.append(reason)
        if cause.get("incomplete_reason") == "max_output_tokens":
            reasons.append("출력 토큰 한도에 도달해 응답이 중단됨")
        if cause.get("incomplete_reason") == "content_filter":
            reasons.append("제공자 콘텐츠 필터로 응답이 중단됨")
        network_kind = cause.get("network_kind")
        network = {"dns": "DNS 조회 실패", "timeout": "네트워크 응답 시간 초과", "tls": "TLS 연결 실패",
                   "connection_refused": "서버 연결 거부", "connection_reset": "연결 끊김",
                   "connection_aborted": "연결 중단", "response_incomplete": "응답 수신 중단", "network": "네트워크 연결 오류"}.get(network_kind) if isinstance(network_kind, str) else None
        if network:
            reasons.append(network)
        if type(cause.get("http_status")) is int:
            reasons.append("HTTP " + str(cause["http_status"]))
    if error.get("stage") == "credentials" and "FileNotFoundError" in names:
        reasons.append("자동 게시 설정 파일 없음 · 운영자 설정을 저장하세요.")
    if "ModuleNotFoundError" in names:
        reasons.append("실행 환경에 필요한 모듈이 없습니다.")
    return stage + "\n" + " → ".join(names) + "\n" + (" / ".join(dict.fromkeys(reasons)) or "저장된 원인 코드가 없어 정확한 원인은 확인할 수 없습니다.")


def run_action(row: dict, running: bool, configured: bool) -> tuple[str, bool]:
    if running:
        return "현재 작업 실행 중", False
    if row["status"] == "completed":
        return "오늘 공식 게시 완료", False
    if not configured:
        return "운영자 설정 필요", False
    if row.get("analysis_attempts", 0) >= 2 and not row.get("result_saved"):
        return "오늘 분석 시도 한도 도달", False
    if row.get("result_saved"):
        return "저장된 오늘 결과 게시 재시도", True
    return ("오늘 분석 이어서 실행" if row["status"] in {"failed", "analysis_failed", "attempting", "checkpoint"} else "오늘 분석·공식 게시 실행"), True
