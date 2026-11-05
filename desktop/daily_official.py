"""Windows user-only daily official publishing; credentials use DPAPI."""
import argparse
import ctypes
import json
import os
import subprocess
import sys
import traceback
import uuid
from contextlib import ExitStack
from ctypes import wintypes
from datetime import datetime, timedelta, timezone
from pathlib import Path
from desktop.cloud import CloudNetworkError, OfficialSchemaRequired

ROOT = Path(__file__).resolve().parent.parent
BUNDLE = Path(getattr(sys, "_MEIPASS", ROOT))
DATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "MarketCouncil" / "daily"

def runtime_root() -> Path:
    return DATA.parent if getattr(sys, "frozen", False) else ROOT


def launch_command(*, setup: bool = False) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--daily-setup" if setup else "--daily-official"]
    command = [str(ROOT / "venv" / "Scripts" / "pythonw.exe"), "-m", "desktop.daily_official"]
    return [*command, "--setup"] if setup else command


def install_command() -> list[str]:
    command = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
               str(BUNDLE / "tools" / "install_daily_official.ps1")]
    if getattr(sys, "frozen", False):
        command.extend(["-ExecutablePath", str(Path(sys.executable).resolve())])
    return command


def prepare_runtime(search: str) -> None:
    root = runtime_root()
    root.mkdir(parents=True, exist_ok=True)
    os.chdir(root)
    if not getattr(sys, "frozen", False):
        return
    import shutil
    from app import local_services
    os.environ["HF_HOME"] = str(root / "models")
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(root / "browser")
    infra = root / "infra" / "searxng"
    infra.mkdir(parents=True, exist_ok=True)
    for name in ("docker-compose.yml", "settings.yml"):
        shutil.copyfile(BUNDLE / "infra" / "searxng" / name, infra / name)
    local_services.PROJECT_ROOT = root
    local_services.COMPOSE_FILE = infra / "docker-compose.yml"
    local_services.SEARXNG_URL = search


def ensure_browser() -> None:
    if not getattr(sys, "frozen", False):
        return
    root = runtime_root()
    if (root / "browser-ready").exists():
        return
    with (root / "browser-install.log").open("w", encoding="utf-8") as output:
        completed = subprocess.run([sys.executable, "--install-browser"], stdout=output,
                                   stderr=output, timeout=600,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if completed.returncode:
        raise RuntimeError("브라우저 준비 실패. 로컬 browser-install.log를 확인하세요.")
    (root / "browser-ready").write_text("ready", encoding="utf-8")


class Blob(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]

def crypt(data: bytes, decrypt: bool = False) -> bytes:
    if os.name != "nt": raise RuntimeError("Windows 계정 암호화가 필요합니다.")
    buf = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    api = ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
    if not api(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise ctypes.WinError()
    try: return ctypes.string_at(target.data, target.size)
    finally: ctypes.windll.kernel32.LocalFree(target.data)

def save_credentials(data: dict) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    target = DATA / "credentials.dpapi"
    temporary = target.with_suffix(".tmp")
    temporary.write_bytes(crypt(json.dumps(data).encode()))
    temporary.replace(target)

def credentials() -> dict:
    return json.loads(crypt((DATA / "credentials.dpapi").read_bytes(), True))

def today() -> str:
    return datetime.now(timezone(timedelta(hours=9))).date().isoformat()

def save_state(state: dict) -> None:
    temporary = DATA / "state.tmp"
    temporary.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    temporary.replace(DATA / "state.json")

def run_once(state: dict, day: str, prepare, analyze, publish, persist, resume: bool = False, *, target: dict | None = None) -> str:
    if state.get("day") == day and state.get("status") == "completed":
        return "skipped"
    prepare()
    if state.get("day") == day and state.get("status") in ("attempting", "analysis_failed") and (not resume or state.get("analysis_attempts",1)>=2):
        return "skipped"
    if state.get("day") == day and state.get("result_path"):
        path = state["result_path"]
    else:
        attempts=state.get("analysis_attempts",1)+1 if state.get("day")==day else 1
        state.clear(); state.update(day=day, status="attempting", analysis_attempts=attempts)
        if target: state["target"] = dict(target)
        persist(state)
        try: path = analyze()
        except Exception:
            state["status"] = "analysis_failed"; persist(state); raise
        state.update(result_path=str(path), status="pending_upload"); persist(state)
    publish(path)
    state["status"] = "completed"; persist(state)
    return "completed"

def prepare_target(config: dict, state: dict, day: str, session: dict) -> dict:
    """Choose before a paid attempt, and never switch an unfinished day's company."""
    from app.evidence_preflight import prepare_company, require_company_ready
    from desktop.cloud import check_official_result, official_history
    from tools.company_profiles import PROFILES, get_profile
    from tools.evidence_readiness import select_official_candidate, validate_readiness_report
    same_day = state.get("day") == day
    pinned = state.get("target") if same_day else None
    if same_day and state.get("result_path"):
        result = json.loads(Path(state["result_path"]).read_text(encoding="utf-8"))
        report = check_official_result(result, day)
        profile = get_profile(result["company_name"], result["financial_data"]["ticker"])
        if pinned and ((pinned.get("company_name"), pinned.get("ticker")) != (profile["company_name"], profile["ticker"])
                       or (pinned.get("readiness_report") or {}).get("corpus_hash") != report["corpus_hash"]):
            raise ValueError("저장한 결과와 오늘 고정한 기업 또는 근거가 다릅니다. 자동 재분석하지 않습니다.")
        return {"company_name": profile["company_name"], "ticker": profile["ticker"], "readiness_report": report}
    # Old interrupted Samsung jobs must not silently resume as a different company.
    if pinned or (same_day and state.get("status") in ("attempting", "analysis_failed")):
        profile = get_profile(pinned["company_name"], pinned["ticker"]) if pinned else get_profile("삼성전자", "005930.KS")
        _,report = require_company_ready(profile["company_name"], profile["ticker"], refresh=False, base_dir=DATA.parent/"company-evidence")
        previous = pinned.get("readiness_report") if pinned else None
        if previous and previous.get("corpus_hash") != report.get("corpus_hash"):
            raise ValueError("복구할 분석의 근거가 변경됐습니다. 기존 체크포인트와 결과를 보존하고 자동 재분석을 중지합니다.")
    elif config.get("official_mode", "samsung") == "samsung":
        profile = get_profile("삼성전자", "005930.KS")
        _,report = require_company_ready(profile["company_name"], profile["ticker"], base_dir=DATA.parent/"company-evidence")
    elif config.get("official_mode") == "eligible":
        history = official_history(session)
        reports = []
        for profile in PROFILES:
            _,report = prepare_company(profile["company_name"], profile["ticker"], base_dir=DATA.parent/"company-evidence")
            reports.append(report)
        report = select_official_candidate(reports, history, day)
        if report is None:
            raise ValueError("오늘 기준 근거가 충분한 기업이 없어 유료 분석과 공식 게시를 시작하지 않습니다.")
        profile = get_profile(report["company_name"], report["ticker"])
    else:
        raise ValueError("공식 게시 기업 선택 설정을 확인하세요.")
    report = validate_readiness_report(report, profile["company_name"], profile["ticker"])
    if report["status"] != "ready" or report["as_of_date"] != day:
        raise ValueError("오늘 기준 근거가 충분한 기업만 분석할 수 있습니다.")
    return {"company_name": profile["company_name"], "ticker": profile["ticker"], "readiness_report": report}


def notify(message: str) -> None:
    # A completion alarm must not keep the scheduled task alive awaiting a click.
    window = None
    try:
        import tkinter as tk
        from tkinter import ttk
        window = tk.Tk()
        window.title("MarketCouncil 자동 공식 토론")
        window.attributes("-topmost", True)
        ttk.Label(window, text=message, wraplength=440, padding=16).pack()
        ttk.Button(window, text="확인", command=window.destroy).pack(pady=(0, 12))
        window.after(8000, window.destroy)
        window.mainloop()
    except Exception:
        # Notification failure must not turn a completed publication into a failed run.
        if window is not None:
            try: window.destroy()
            except Exception: pass

def failure_record(stage: str, error: Exception) -> dict:
    record = {"day": today(), "stage": stage, "error_type": type(error).__name__, "credentials_present": (DATA / "credentials.dpapi").exists()}
    if isinstance(error, OSError): record["winerror"] = error.winerror if hasattr(error, "winerror") else None
    if isinstance(error, ModuleNotFoundError): record["module"] = error.name
    chain=[]; seen=set(); current=error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        entry={"type":type(current).__name__, "locations":[{"file":Path(frame.filename).name,"function":frame.name,"line":frame.lineno} for frame in traceback.extract_tb(current.__traceback__)[-4:]]}
        for key in ("response_status","incomplete_reason"):
            value=getattr(current,key,None)
            if value in {"completed","incomplete","failed","max_output_tokens","content_filter"}:entry[key]=value
        status=getattr(current,"status_code",None)
        if isinstance(status,int):entry["http_status"]=status
        code=getattr(current,"code",None)
        if code in {"insufficient_quota","credit_balance_exhausted","rate_limit_exceeded","invalid_api_key","context_length_exceeded"}:entry["api_code"]=code
        if isinstance(current, CloudNetworkError):
            if current.network_kind in {"dns", "timeout", "tls", "response_incomplete", "connection_refused", "connection_reset", "connection_aborted", "network"}:
                entry["network_kind"] = current.network_kind
            if type(current.attempts) is int and 1 <= current.attempts <= 3:
                entry["attempts"] = current.attempts
            if type(current.retry_allowed) is bool:
                entry["retry_allowed"] = current.retry_allowed
            for key in ("errno", "winerror"):
                value = getattr(current, key, None)
                if type(value) is int:
                    entry[key] = value
        chain.append(entry);current=current.__cause__
    record["causes"]=chain
    return record

def source_version() -> str:
    if getattr(sys, "frozen", False):
        import re
        from desktop.preferences import VERSION
        try:
            metadata = json.loads((BUNDLE / "release-build.json").read_text(encoding="utf-8"))
            commit = metadata.get("source_commit") if isinstance(metadata, dict) else None
            if isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{40}", commit) and metadata.get("version") == VERSION:
                return commit
        except (OSError, ValueError):
            pass
        return "unknown"
    try:
        result=subprocess.run(["git","rev-parse","--short","HEAD"],cwd=ROOT,capture_output=True,text=True,timeout=2,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        value=result.stdout.strip()
        return value if result.returncode==0 and value and all(c in "0123456789abcdef" for c in value) else "unknown"
    except (OSError,subprocess.TimeoutExpired):return "unknown"

def save_failure(stage: str, error: Exception, run_id: str) -> None:
    folder=DATA/"errors";folder.mkdir(parents=True,exist_ok=True)
    latest=DATA/"last-error.json";legacy=folder/"legacy-first-error.json"
    if latest.exists() and not legacy.exists():
        # Existing generated metadata is preserved before replacing the latest pointer.
        legacy.write_bytes(latest.read_bytes())
    record={**failure_record(stage,error),"run_id":run_id,"recorded_at":datetime.now(timezone.utc).isoformat(),"source_version":source_version()}
    filename=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")+"-"+run_id+".json"
    (folder/filename).write_text(json.dumps(record,ensure_ascii=False),encoding="utf-8")
    temporary=latest.with_suffix(".tmp");temporary.write_text(json.dumps(record,ensure_ascii=False),encoding="utf-8");temporary.replace(latest)

def run() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    import msvcrt
    with (DATA / "run.lock").open("a+b") as lock:
        lock.seek(0); lock.write(b"0"); lock.flush(); lock.seek(0)
        try: msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError: return 0
        run_id=uuid.uuid4().hex
        os.environ["RESULTS_RUN_ID"]=run_id
        os.environ["RESULTS_SOURCE_VERSION"]=source_version()
        stage = "credentials"
        services = ExitStack()
        def record_cleanup_error(service: str) -> None:
            stage = {"SearXNG": "cleanup_search", "Docker Desktop": "cleanup_docker"}[service]
            save_failure(stage, RuntimeError("Local service cleanup failed"), run_id)
        def close_services() -> None:
            try: services.close()
            except Exception as error:
                try: save_failure("cleanup", error, run_id)
                except Exception: pass
        try:
            config = credentials()
            state_path = DATA / "state.json"
            state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
            from desktop.cloud import request, upload_result, official_selection, select_official, check_official_schema
            session = {}
            day = today()
            target = {}
            def prepare() -> None:
                nonlocal stage
                stage = "account"
                session.update(request("/auth/v1/token?grant_type=refresh_token", {"refresh_token": config["refresh_token"]}))
                config["refresh_token"] = session["refresh_token"]; save_credentials(config)
                if request("/rest/v1/rpc/is_official_editor", {}, session["access_token"]) is not True:
                    raise RuntimeError("operator")
                if today()!=day: raise ValueError("한국 날짜가 바뀌어 새 분석을 시작하지 않습니다.")
                rows = official_selection(session, day)
                if rows:
                    save_state({"day": day, "status": "completed"})
                    raise AlreadyPublished()
                check_official_schema(session, day)
                if not target and not (state.get("day")==day and state.get("status") in ("attempting","analysis_failed") and state.get("analysis_attempts",1)>=2):
                    stage = "evidence"
                    os.environ["DART_API_KEY"]=config.get("dart_key", "")
                    if config.get("sec_user_agent"):os.environ["SEC_USER_AGENT"]=config["sec_user_agent"]
                    target.update(prepare_target(config,state,day,session))
            def analyze() -> str:
                nonlocal stage
                if today()!=day: raise ValueError("한국 날짜가 바뀌어 새 분석을 시작하지 않습니다.")
                stage = "services"
                company=target["company_name"];ticker=target["ticker"]
                os.environ.update(OPENAI_API_KEY=config["openai_key"], DART_API_KEY=config.get("dart_key", ""), SEARXNG_URL=config["search"], MARKETCOUNCIL_COMPANY=company, MARKETCOUNCIL_TICKER=ticker, CHROMA_MODE="local", RESULTS_AUTO_UPLOAD="false")
                prepare_runtime(config["search"])
                from app.local_services import daily_local_services
                services.enter_context(daily_local_services(record_cleanup_error))
                ensure_browser()
                stage = "analysis"
                from app.recoverable_debate_workflow import RecoverableDebateWorkflow
                from tools.analysis_debate_store import AnalysisDebateStore
                from tools.debate_transcript_renderer import DebateTranscriptRenderer
                from tools.run_metrics import measure_analysis
                os.environ["RESULTS_RESPONSE_METRICS_DIR"]=str(DATA / "response-metrics")
                import hashlib
                corpus_hash=target["readiness_report"]["corpus_hash"]
                identity=hashlib.sha256((company+"|"+ticker+"|"+corpus_hash).encode()).hexdigest()[:16]
                checkpoint=DATA/("analysis-"+day+"-"+identity+".json")
                result = measure_analysis(company, lambda: RecoverableDebateWorkflow(checkpoint,company,day,ticker=ticker,corpus_hash=corpus_hash).run(company), DATA.parent / "metrics")
                result.setdefault("readiness_report",target["readiness_report"])
                path = Path(AnalysisDebateStore().save(company, result)).resolve()
                DebateTranscriptRenderer().save(result)
                return str(path)
            def publish(path: str) -> None:
                nonlocal stage
                stage = "result"
                import hashlib, uuid
                result = json.loads(Path(path).read_text(encoding="utf-8"))
                from desktop.cloud import check_official_result
                check_official_result(result,state["day"])
                if result.get("company_name") != target["company_name"] or result.get("financial_data", {}).get("ticker") != target["ticker"]:
                    raise ValueError("저장한 결과와 오늘 고정한 기업이 다릅니다.")
                # Refresh after a long analysis; persist rotated tokens before another task.
                prepare()
                if state["day"] != today(): raise RuntimeError("date changed")
                identifier = str(uuid.uuid5(uuid.NAMESPACE_URL, session["user"]["id"] + hashlib.sha256(json.dumps(result, sort_keys=True, ensure_ascii=False).encode()).hexdigest()))
                stage = "publish"
                upload_result(result, session, identifier)
                select_official(session, identifier, state["day"])
            outcome = run_once(state, day, prepare, analyze, publish, save_state, resume=True,target=target)
            close_services()
            if outcome == "completed": notify("오늘 "+target.get("company_name","선택 기업")+" 공식 토론 게시가 완료됐습니다. 웹 커뮤니티에서 확인하세요.")
            elif state.get("status") in ("attempting", "analysis_failed"):
                notify("오늘 분석이 중단되거나 실패했습니다. 오늘 복구 시도 한도에 도달해 더 실행하지 않습니다. 로컬 결과와 실행 환경을 확인하세요.")
            return 0
        except AlreadyPublished: return 0
        except Exception as error:
            close_services()
            try:
                save_failure(stage,error,run_id)
                note="상세 원인은 운영자용 로컬 기록에 저장했습니다."
            except OSError:note="로컬 진단 기록 저장도 실패했습니다. 저장 공간과 권한을 확인하세요."
            if isinstance(error, OfficialSchemaRequired):
                notify(str(error)+" "+note)
            else:
                notify("자동 분석 또는 게시에 실패했습니다. 기존 결과는 유지됩니다. "+note)
            return 1
        finally:
            try: close_services()
            finally:
                lock.seek(0); msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)

class AlreadyPublished(Exception): pass

def setup() -> None:
    import tkinter as tk
    from tkinter import ttk, messagebox
    from dotenv import dotenv_values
    from desktop.cloud import send_login, login_link, request
    defaults = {} if getattr(sys, "frozen", False) else dotenv_values(ROOT / ".env")
    try: previous=credentials()
    except (OSError,ValueError):previous={}
    window = tk.Tk(); window.title("MarketCouncil 매일 공식 게시 설정"); window.geometry("640x720")
    ttk.Label(window, text="로그인 시 및 매일 오전 9시 확인 · 하루 1회 분석 후 공식 공개", wraplength=600).pack(pady=12)
    ttk.Label(window,text="분석 대상 · 기존 저장 설정은 삼성전자 고정을 유지합니다.").pack(anchor="w",padx=20)
    mode=ttk.Combobox(window,state="readonly",values=("삼성전자 고정 · 근거 충족 시만 실행","준비된 6개 기업 · 새 공시 우선, 오래 미게시한 기업 순"))
    mode.pack(fill="x",padx=20,pady=4);mode.current(1)
    fields = {}
    for name, label, default, secret in [("email", "공식 운영자 이메일", "" if getattr(sys, "frozen", False) else "tkftor8544@gmail.com", False), ("key", "OpenAI 키 · Windows 계정에 암호화 저장", defaults.get("OPENAI_API_KEY", ""), True), ("dart", "DART 키 (국내 공시 원문용) · Windows 계정에 암호화 저장", defaults.get("DART_API_KEY", ""), True), ("sec", "SEC 수집 연락처·User-Agent (선택, SEC 요청 헤더로 전송)", previous.get("sec_user_agent") or defaults.get("SEC_USER_AGENT") or os.getenv("SEC_USER_AGENT", ""), False), ("search", "검색 서비스", defaults.get("SEARXNG_URL", "http://127.0.0.1:8080"), False), ("link", "메일의 로그인 버튼 링크 복사 후 붙여넣기", "", True)]:
        ttk.Label(window, text=label).pack(anchor="w", padx=20)
        entry = ttk.Entry(window, show="•" if secret else ""); entry.pack(fill="x", padx=20, pady=4); entry.insert(0, default or ""); fields[name] = entry
    def mail() -> None:
        try: send_login(fields["email"].get()); messagebox.showinfo("메일 발송", "메일의 로그인 버튼을 클릭하지 말고 링크 주소를 복사해 아래 칸에 붙여넣으세요.")
        except Exception: messagebox.showerror("발송 실패", "메일 주소와 인터넷 연결을 확인하세요.")
    def save() -> None:
        try:
            key = fields["key"].get().strip()
            if not key: raise ValueError("key")
            from urllib.parse import urlsplit
            parsed = urlsplit(fields["search"].get().strip())
            if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password: raise ValueError("search")
            session = login_link(fields["link"].get())
            if session["user"].get("email", "").lower() != fields["email"].get().strip().lower(): raise ValueError("email")
            if request("/rest/v1/rpc/is_official_editor", {}, session["access_token"]) is not True: raise ValueError("operator")
            save_credentials({"openai_key": key, "dart_key": fields["dart"].get().strip(), "search": fields["search"].get().strip(), "refresh_token": session["refresh_token"], "official_mode": "eligible" if mode.current()==1 else "samsung", "sec_user_agent": fields["sec"].get().strip()})
            completed = subprocess.run(install_command(), capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            if completed.returncode: raise RuntimeError("scheduler")
            (DATA / "setup-complete").write_text("configured", encoding="utf-8")
            messagebox.showinfo("설정 완료", "Windows 로그인과 매일 오전 9시에 자동 확인합니다. 선택한 모드에서 근거가 충분한 기업만 분석합니다. 오늘 실행을 시작하며 분석 결과와 근거는 공식 공개됩니다.")
            subprocess.Popen(launch_command(), cwd=runtime_root(), creationflags=subprocess.CREATE_NO_WINDOW)
            window.destroy()
        except Exception: messagebox.showerror("설정 실패", "키·검색 주소와 새 로그인 링크, 공식 운영자 권한을 확인하세요. 일정 등록에 실패한 경우 설정을 다시 저장하세요.")
    ttk.Button(window, text="로그인 메일 보내기", command=mail).pack(pady=5)
    ttk.Button(window, text="암호화 저장 후 자동 게시 켜기", command=save).pack(pady=10)
    window.mainloop()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--setup", action="store_true"); args = parser.parse_args()
    if args.setup: setup()
    else: raise SystemExit(run())
