"""Windows desktop entry point. Keys and login sessions live in memory only."""
import os
import sys
import json
import uuid
import queue
import threading
import subprocess
import webbrowser
from pathlib import Path
from typing import Callable
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

DATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "MarketCouncil"


class Output:
    def __init__(self, messages: queue.Queue) -> None:
        self.messages = messages
        self.pending = ""
    def write(self, text: str) -> int:
        if text:
            self.messages.put(text)
            self.pending=(self.pending+text)[-4000:]
            from desktop.readiness import stage_for_line
            while "\n" in self.pending:
                line,self.pending=self.pending.split("\n",1)
                stage=stage_for_line(line)
                if stage:self.messages.put(("stage",stage))
        return len(text)
    def flush(self) -> None:
        pass


class Desktop:
    def __init__(self, root: tk.Tk) -> None:
        self.root=root;root.title("MarketCouncil · 개인 분석");root.geometry("900x850");root.minsize(760,800)
        self.messages=queue.Queue();self.session=None;self.busy=False;self.loaded_settings=None
        self.result_path=None;self.result_id=None
        panel=ttk.Frame(root,padding=24);panel.pack(fill="both",expand=True)
        ttk.Label(panel,text="MarketCouncil",font=("Segoe UI",24,"bold")).pack(anchor="w")
        ttk.Label(panel,text="내 PC에서 분석하고, 원하는 결과만 내 계정에 보관합니다.").pack(anchor="w",pady=(0,16))
        tabs=ttk.Notebook(panel);tabs.pack(fill="x",pady=8)
        account_panel=ttk.Frame(tabs,padding=12);analysis_panel=ttk.Frame(tabs,padding=12)
        tabs.add(analysis_panel,text="기업 분석");tabs.add(account_panel,text="이메일 계정 연결")
        setup_panel=ttk.Frame(tabs,padding=12);tabs.add(setup_panel,text="준비 상태")
        ttk.Label(setup_panel,text="분석을 시작하기 전에 연결 상태를 확인하세요. API 사용료는 발생하지 않습니다.").pack(anchor="w")
        ttk.Button(setup_panel,text="준비 상태 확인",command=self.check_setup).pack(anchor="w",pady=12)
        self.setup_status=ttk.Label(setup_panel,text="기업 분석 탭에 API 키와 검색 주소를 입력한 뒤 확인하세요.",wraplength=780,justify="left")
        self.setup_status.pack(anchor="w",pady=8)
        ttk.Button(setup_panel,text="Docker 설치 안내",command=lambda:webbrowser.open("https://docs.docker.com/desktop/setup/install/windows-install/")).pack(anchor="w")
        ttk.Label(account_panel,text="GitHub 사용자는 로그인 없이 분석한 뒤 웹 마이페이지에서 결과 JSON을 가져오세요.",wraplength=780).pack(anchor="w")
        self.email=self.field(account_panel,"계정 이메일")
        ttk.Button(account_panel,text="로그인 메일 받기",command=self.send_login).pack(anchor="w")
        self.link=self.field(account_panel,"메일의 로그인 버튼을 우클릭 → 링크 주소 복사 → 아래 붙여넣기",secret=True)
        ttk.Button(account_panel,text="계정 연결",command=self.login).pack(anchor="w")
        self.account=ttk.Label(account_panel,text="로그아웃 상태 · 로컬 분석은 로그인 없이도 가능합니다.");self.account.pack(anchor="w",pady=8)
        ttk.Button(account_panel,text="계정 연결 해제",command=self.disconnect).pack(anchor="w")
        self.key=self.field(analysis_panel,"본인 OpenAI API 키 (이번 실행 동안만 사용)",secret=True)
        self.dart=self.field(analysis_panel,"DART API 키 (국내 공시 수집용, 선택)",secret=True)
        self.search=self.field(analysis_panel,"SearXNG 검색 주소 (Docker Desktop 필요)");self.search.insert(0,"http://127.0.0.1:8080")
        row=ttk.Frame(analysis_panel);row.pack(fill="x",pady=8)
        self.company=self.field(row,"기업명");self.company.insert(0,"삼성전자")
        self.matched_name=None;self.company_candidates=[]
        ttk.Label(row,text="기업명으로 종목을 찾습니다. 해외 기업은 영문 이름을 입력하세요.").pack(anchor="w")
        self.company_choice=ttk.Combobox(row,state="readonly");self.company_choice.pack(fill="x",pady=3)
        ttk.Button(row,text="기업 찾기",command=self.lookup_company).pack(anchor="w")
        buttons=ttk.Frame(analysis_panel);buttons.pack(fill="x",pady=8)
        self.run_button=ttk.Button(buttons,text="내 PC에서 분석 실행",command=self.run);self.run_button.pack(side="left",padx=4)
        self.upload_button=ttk.Button(buttons,text="현재 결과를 내 계정에 업로드 (비공개)",command=self.upload);self.upload_button.pack(side="left",padx=4)
        ttk.Button(buttons,text="저장한 결과 선택",command=self.choose).pack(side="left",padx=4)
        ttk.Button(buttons,text="웹 마이페이지",command=lambda:webbrowser.open("https://frontend-six-pi-h5i7tztups.vercel.app/app?view=my")).pack(side="left",padx=4)
        ttk.Label(panel,text="분석에는 본인 OpenAI 사용료가 발생합니다. PDF·검색 데이터는 PC에 남습니다.").pack(anchor="w")
        self.status=ttk.Label(panel,text="대기 중 · 기업을 선택하고 분석을 시작하세요.",wraplength=780)
        self.status.pack(anchor="w",pady=(8,0))
        self.progress=ttk.Progressbar(panel,mode="indeterminate");self.progress.pack(fill="x",pady=4)
        self.open_result_button=ttk.Button(panel,text="결과 폴더 열기",command=self.open_results)
        self.open_result_button.pack(anchor="w")
        self.log=tk.Text(panel,height=9,wrap="word",state="disabled");self.log.pack(fill="both",expand=True,pady=10)
        root.after(150,self.poll);root.protocol("WM_DELETE_WINDOW",self.close)

    def field(self,parent: ttk.Frame,label: str,secret: bool=False) -> ttk.Entry:
        ttk.Label(parent,text=label).pack(anchor="w",pady=(5,0))
        entry=ttk.Entry(parent,show="•" if secret else "");entry.pack(fill="x",pady=3);return entry

    def open_results(self) -> None:
        folder=DATA/"results";folder.mkdir(parents=True,exist_ok=True)
        if os.name=="nt":os.startfile(folder)
        else:webbrowser.open(folder.as_uri())

    def check_setup(self) -> None:
        key=self.key.get();search=self.search.get().strip()
        def work() -> None:
            from desktop.readiness import check_readiness
            results=check_readiness(key,search,DATA)
            self.messages.put(("readiness","\n\n".join(label+" · "+value for label,value in results)))
        self.task(work,"준비 상태 확인 중 · API 키는 전송하지 않습니다.")

    def task(self, work: Callable[[], None], stage: str="요청 처리 중…") -> None:
        if self.busy:return
        self.status.config(text=stage);self.progress.start(12)
        self.busy=True;self.run_button.config(state="disabled");self.upload_button.config(state="disabled")
        def wrapper() -> None:
            try: work()
            except Exception as error:
                detail=str(error) if isinstance(error,(ValueError,RuntimeError)) else type(error).__name__
                self.messages.put(("stage","실패 · 준비 상태 탭과 아래 기록을 확인하세요. 키·권한 문제는 계정 설정을, 검색 문제는 Docker와 인터넷 연결을 확인하세요."))
                self.messages.put("실행 실패: "+detail+"\n")
                self.messages.put(("failed",None))
            finally:self.messages.put(("done",None))
        threading.Thread(target=wrapper,daemon=True).start()

    def send_login(self) -> None:
        email=self.email.get().strip()
        if "@" not in email:messagebox.showerror("이메일","이메일을 입력하세요.");return
        def work() -> None:
            from desktop.cloud import send_login
            send_login(email);self.messages.put("로그인 메일을 보냈습니다. 메일 버튼의 링크 주소를 복사해 계정 연결에 붙여넣으세요.\n")
        self.task(work)

    def login(self) -> None:
        link=self.link.get()
        def work() -> None:
            from desktop.cloud import login_link
            self.session=login_link(link);self.messages.put(("login",self.session["user"]["email"]))
        self.task(work)

    def lookup_company(self) -> None:
        if self.busy:return
        name=self.company.get().strip()
        self.matched_name=None;self.company_candidates=[];self.company_choice.set("")
        def work() -> None:
            from tools.company_lookup import find_companies
            candidates=find_companies(name)
            if not candidates:raise ValueError("일치하는 상장 기업이 없습니다. 정식 기업명을 확인하세요. 해외 기업은 영문 이름을 입력하세요.")
            self.messages.put(("companies",(name,candidates)))
        self.task(work)

    def run(self) -> None:
        company=self.company.get().strip();key=self.key.get().strip();dart=self.dart.get().strip();search=self.search.get().strip()
        if self.busy:return
        if not company or len(company)>120 or not key:
            messagebox.showerror("입력 확인","기업명과 본인 OpenAI 키를 입력하세요.");return
        if company!=self.matched_name:
            self.lookup_company();return
        selected=self.company_choice.current()
        if selected<0:
            messagebox.showinfo("기업 선택","검색된 후보에서 분석할 기업을 선택하세요.");return
        candidate=self.company_candidates[selected];company=candidate["name"];ticker=candidate["ticker"]
        if self.loaded_settings and self.loaded_settings!=(key,dart,search):messagebox.showinfo("설정 변경","API 키나 검색 주소를 바꾸려면 프로그램을 다시 실행하세요.");return
        if not messagebox.askyesno("분석 실행","본인 PC에서 분석을 실행합니다. OpenAI 사용료가 발생하며 수 분 이상 걸릴 수 있습니다. 실행할까요?"):return
        def work() -> None:
            os.environ.update(OPENAI_API_KEY=key,DART_API_KEY=dart,SEARXNG_URL=search,MARKETCOUNCIL_TICKER=ticker,CHROMA_MODE="local",RESULTS_AUTO_UPLOAD="false")
            self.messages.put(("stage","분석 준비 · 로컬 저장 공간과 검색 서비스를 준비합니다."))
            DATA.mkdir(parents=True,exist_ok=True);os.chdir(DATA)
            os.environ["HF_HOME"]=str(DATA/"models")
            from app import local_services
            bundle=Path(getattr(sys,"_MEIPASS",Path(__file__).resolve().parent.parent))
            import shutil
            infra=DATA/"infra"/"searxng";infra.mkdir(parents=True,exist_ok=True)
            for filename in ("docker-compose.yml","settings.yml"):
                shutil.copyfile(bundle/"infra"/"searxng"/filename,infra/filename)
            local_services.COMPOSE_FILE=infra/"docker-compose.yml"
            local_services.PROJECT_ROOT=DATA;local_services.SEARXNG_URL=search
            from contextlib import redirect_stdout,redirect_stderr
            with redirect_stdout(Output(self.messages)),redirect_stderr(Output(self.messages)):
                local_services.ensure_local_services()
                os.environ["PLAYWRIGHT_BROWSERS_PATH"]=str(DATA/"browser")
                if not (DATA/"browser-ready").exists():
                    self.messages.put(("stage","첫 실행 준비 · 자료 수집 브라우저 다운로드 중입니다."))
                    self.messages.put("첫 실행 웹 자료 수집용 브라우저를 다운로드합니다.\n")
                    command=[sys.executable,"--install-browser"] if getattr(sys,"frozen",False) else [sys.executable,"-m","playwright","install","chromium"]
                    with (DATA/"browser-install.log").open("w",encoding="utf-8") as output:
                        outcome=subprocess.run(command,stdout=output,stderr=output,timeout=600,creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
                    if outcome.returncode:raise RuntimeError("브라우저 준비 실패. 로컬 browser-install.log를 확인하세요.")
                    (DATA/"browser-ready").write_text("ready",encoding="utf-8")
                self.loaded_settings=(key,dart,search)
                from app.debate_workflow import DebateWorkflow
                from tools.analysis_debate_store import AnalysisDebateStore
                from tools.debate_transcript_renderer import DebateTranscriptRenderer
                result=DebateWorkflow().run(company)
                self.messages.put(("stage","로컬 저장 · 분석 결과와 토론 기록을 저장합니다."))
                self.result_path=Path(AnalysisDebateStore().save(company,result)).resolve()
                DebateTranscriptRenderer().save(result)
            self.messages.put(("stage","분석 완료 · 결과 폴더에서 JSON을 확인하고 웹 마이페이지로 가져오세요."))
            self.result_id=str(uuid.uuid4());self.messages.put("분석 완료 · 로컬 저장: "+str(self.result_path)+"\n계정 업로드 버튼을 누르기 전에는 결과가 PC에만 저장됩니다.\n")
        self.task(work)

    def disconnect(self) -> None:
        if not self.busy:
            self.session=None;self.account.config(text="로그아웃 상태");self.link.delete(0,"end")

    def choose(self) -> None:
        if self.busy:return
        filename=filedialog.askopenfilename(initialdir=str(DATA/"results"),filetypes=[("분석 JSON","*.json")])
        if filename:self.result_path=Path(filename);self.result_id=str(uuid.uuid4());self.messages.put("선택한 로컬 결과: "+self.result_path.name+"\n")

    def upload(self) -> None:
        if not self.session or not self.result_path:messagebox.showinfo("업로드","계정 연결과 저장된 결과 선택이 필요합니다.");return
        def work() -> None:
            from desktop.cloud import request,upload_result
            if self.session.get("refresh_token"):
                self.session=request("/auth/v1/token?grant_type=refresh_token",{"refresh_token":self.session["refresh_token"]})
            data=json.loads(self.result_path.read_text(encoding="utf-8"))
            import hashlib
            self.result_id=str(uuid.uuid5(uuid.NAMESPACE_URL,self.session["user"]["id"]+hashlib.sha256(self.result_path.read_bytes()).hexdigest()))
            upload_result(data,self.session,self.result_id)
            self.messages.put("내 계정에 비공개로 업로드했습니다. 웹 마이페이지에서 열람·공유·게시할 수 있습니다.\n")
        self.task(work)

    def poll(self) -> None:
        while not self.messages.empty():
            event=self.messages.get()
            if isinstance(event,tuple):
                if event[0]=="done":self.progress.stop();self.busy=False;self.run_button.config(state="normal");self.upload_button.config(state="normal");self.status.config(text="요청 완료 · 아래 기록을 확인하세요." if self.status.cget("text")=="요청 처리 중…" else self.status.cget("text"))
                elif event[0]=="stage":self.status.config(text=event[1])
                elif event[0]=="readiness":self.setup_status.config(text=event[1]);self.status.config(text="준비 상태 확인 완료 · 준비 상태 탭의 안내를 확인하세요.")
                elif event[0]=="failed":pass
                elif event[0]=="companies":
                    name,candidates=event[1]
                    if self.company.get().strip()==name:
                        self.matched_name=name;self.company_candidates=candidates
                        self.company_choice.config(values=[f'{item["name"]} · {item["exchange"]} · {item["ticker"]}' for item in candidates])
                        if len(candidates)==1:self.company_choice.current(0)
                        self.messages.put("기업 검색 완료 · 후보를 확인하고 분석 실행을 눌러주세요.\n")
                elif event[0]=="login":self.account.config(text="연결된 계정: "+event[1]);self.link.delete(0,"end")
            else:self.log.config(state="normal");self.log.insert("end",event);self.log.see("end");self.log.config(state="disabled")
        self.root.after(150,self.poll)

    def close(self) -> None:
        if self.busy and not messagebox.askyesno("실행 중","종료하면 진행 중인 분석이 중단될 수 있습니다. 종료할까요?"):return
        self.root.destroy()


if __name__=="__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    if "--install-browser" in sys.argv:
        DATA.mkdir(parents=True,exist_ok=True)
        if sys.stdout is None:sys.stdout=(DATA/"browser-driver.log").open("w",encoding="utf-8");sys.stderr=sys.stdout
        from playwright.__main__ import main
        sys.argv=["playwright","install","chromium"]
        main()
    elif "--self-check" in sys.argv:
        output_path=Path(sys.argv[sys.argv.index("--self-check")+1])
        try:
            from desktop.cloud import PUBLIC_KEY
            os.environ["OPENAI_API_KEY"]="self-check-not-a-real-key"
            os.environ["CHROMA_MODE"]="local"
            from tools.financial_data import TICKER_MAP
            from app.debate_workflow import DebateWorkflow
            from rag.retriever import ReportRetriever
            from playwright.__main__ import main
            from playwright._impl._driver import compute_driver_executable
            assert all(Path(item).exists() for item in compute_driver_executable())
            from crawl4ai import AsyncWebCrawler, BrowserConfig
            from crawl4ai.js_snippet import load_js_script
            assert load_js_script("navigator_overrider")
            import tempfile
            with tempfile.TemporaryDirectory(prefix="marketcouncil-check-",ignore_cleanup_errors=True) as temporary:
                os.chdir(temporary)
                workflow=DebateWorkflow()
                assert workflow.evidence_workflow.bull_tools.retriever.collection.count()==0
                workflow.evidence_workflow.bull_tools.retriever.client._system.stop()
                os.chdir(output_path.parent)
            root=tk.Tk();root.withdraw();ui=Desktop(root)
            assert ui.run_button.winfo_exists()
            root.destroy()
            assert PUBLIC_KEY.startswith("sb_publishable_")
            output_path.write_text("desktop imports OK",encoding="utf-8")
        except Exception:
            import traceback
            output_path.write_text(traceback.format_exc(),encoding="utf-8")
            sys.exit(1)
    else:
        Desktop(tk.Tk()).root.mainloop()
