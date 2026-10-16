"""Windows user-only daily Samsung publishing; credentials use DPAPI."""
import argparse
import ctypes
import json
import os
import subprocess
import sys
import traceback
import uuid
from ctypes import wintypes
from datetime import datetime, timedelta, timezone
from pathlib import Path
from desktop.cloud import OfficialSchemaRequired

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "MarketCouncil" / "daily"

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

def run_once(state: dict, day: str, prepare, analyze, publish, persist, resume: bool = False) -> str:
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
        persist(state)
        try: path = analyze()
        except Exception:
            state["status"] = "analysis_failed"; persist(state); raise
        state.update(result_path=str(path), status="pending_upload"); persist(state)
    publish(path)
    state["status"] = "completed"; persist(state)
    return "completed"

def notify(message: str) -> None:
    # Native dialog is intentional: the user requested a startup/completion alarm.
    ctypes.windll.user32.MessageBoxW(None, message, "MarketCouncil 자동 공식 토론", 0x40 | 0x10000)

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
        chain.append(entry);current=current.__cause__
    record["causes"]=chain
    return record

def source_version() -> str:
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
        try:
            config = credentials()
            state_path = DATA / "state.json"
            state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
            from desktop.cloud import request, upload_result, official_selection, select_official, check_official_schema
            session = {}
            def prepare() -> None:
                nonlocal stage
                stage = "account"
                session.update(request("/auth/v1/token?grant_type=refresh_token", {"refresh_token": config["refresh_token"]}))
                config["refresh_token"] = session["refresh_token"]; save_credentials(config)
                if request("/rest/v1/rpc/is_official_editor", {}, session["access_token"]) is not True:
                    raise RuntimeError("operator")
                rows = official_selection(session, today())
                if rows:
                    save_state({"day": today(), "status": "completed"})
                    raise AlreadyPublished()
                check_official_schema(session, today())
            def analyze() -> str:
                nonlocal stage
                stage = "services"
                os.chdir(ROOT)
                os.environ.update(OPENAI_API_KEY=config["openai_key"], DART_API_KEY=config.get("dart_key", ""), SEARXNG_URL=config["search"], MARKETCOUNCIL_TICKER="005930.KS", CHROMA_MODE="local", RESULTS_AUTO_UPLOAD="false")
                from app.local_services import ensure_local_services
                ensure_local_services()
                stage = "analysis"
                from app.recoverable_debate_workflow import RecoverableDebateWorkflow
                from tools.analysis_debate_store import AnalysisDebateStore
                from tools.debate_transcript_renderer import DebateTranscriptRenderer
                from tools.run_metrics import measure_analysis
                os.environ["RESULTS_RESPONSE_METRICS_DIR"]=str(DATA / "response-metrics")
                workflow=RecoverableDebateWorkflow(DATA / ("analysis-"+today()+".json"),"삼성전자",today())
                result = measure_analysis("삼성전자", lambda: workflow.run("삼성전자"), DATA.parent / "metrics")
                path = Path(AnalysisDebateStore().save("삼성전자", result)).resolve()
                DebateTranscriptRenderer().save(result)
                return str(path)
            def publish(path: str) -> None:
                nonlocal stage
                stage = "result"
                import hashlib, uuid
                result = json.loads(Path(path).read_text(encoding="utf-8"))
                if result.get("company_name") != "삼성전자" or result.get("financial_data", {}).get("ticker") != "005930.KS":
                    raise ValueError("unexpected company")
                # Refresh after a long analysis; persist rotated tokens before another task.
                prepare()
                if state["day"] != today(): raise RuntimeError("date changed")
                identifier = str(uuid.uuid5(uuid.NAMESPACE_URL, session["user"]["id"] + hashlib.sha256(json.dumps(result, sort_keys=True, ensure_ascii=False).encode()).hexdigest()))
                stage = "publish"
                upload_result(result, session, identifier)
                select_official(session, identifier, state["day"])
            outcome = run_once(state, today(), prepare, analyze, publish, save_state, resume=True)
            if outcome == "completed": notify("오늘 삼성전자 공식 토론 게시가 완료됐습니다. 웹 커뮤니티에서 확인하세요.")
            elif state.get("status") in ("attempting", "analysis_failed"):
                notify("오늘 분석이 중단되거나 실패했습니다. 오늘 복구 시도 한도에 도달해 더 실행하지 않습니다. 로컬 결과와 실행 환경을 확인하세요.")
            return 0
        except AlreadyPublished: return 0
        except Exception as error:
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
            lock.seek(0); msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)

class AlreadyPublished(Exception): pass

def setup() -> None:
    import tkinter as tk
    from tkinter import ttk, messagebox
    from dotenv import dotenv_values
    from desktop.cloud import send_login, login_link, request
    defaults = dotenv_values(ROOT / ".env")
    window = tk.Tk(); window.title("MarketCouncil 매일 삼성전자 자동 게시 설정"); window.geometry("640x460")
    ttk.Label(window, text="로그인 시 및 매일 오전 9시 확인 · 하루 1회 분석 후 공식 공개", wraplength=600).pack(pady=12)
    fields = {}
    for name, label, default, secret in [("email", "공식 운영자 이메일", "tkftor8544@gmail.com", False), ("key", "OpenAI 키 · Windows 계정에 암호화 저장", defaults.get("OPENAI_API_KEY", ""), True), ("search", "검색 서비스", defaults.get("SEARXNG_URL", "http://127.0.0.1:8080"), False), ("link", "메일의 로그인 버튼 링크 복사 후 붙여넣기", "", True)]:
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
            save_credentials({"openai_key": key, "dart_key": defaults.get("DART_API_KEY", ""), "search": fields["search"].get().strip(), "refresh_token": session["refresh_token"]})
            completed = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "tools" / "install_daily_official.ps1")], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            if completed.returncode: raise RuntimeError("scheduler")
            (DATA / "setup-complete").write_text("configured", encoding="utf-8")
            messagebox.showinfo("설정 완료", "Windows 로그인과 매일 오전 9시에 자동 확인합니다. 오늘 실행을 시작합니다. 분석 결과와 근거는 공식 공개됩니다.")
            subprocess.Popen([str(ROOT / "venv" / "Scripts" / "pythonw.exe"), "-m", "desktop.daily_official"], cwd=ROOT, creationflags=subprocess.CREATE_NO_WINDOW)
            window.destroy()
        except Exception: messagebox.showerror("설정 실패", "키·검색 주소와 새 로그인 링크, 공식 운영자 권한을 확인하세요. 일정 등록에 실패한 경우 설정을 다시 저장하세요.")
    ttk.Button(window, text="로그인 메일 보내기", command=mail).pack(pady=5)
    ttk.Button(window, text="암호화 저장 후 자동 게시 켜기", command=save).pack(pady=10)
    window.mainloop()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--setup", action="store_true"); args = parser.parse_args()
    if args.setup: setup()
    else: raise SystemExit(run())
