"""Ask before a paid daily run; closing this window never starts analysis."""
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText

from desktop import daily_official as daily
from desktop.daily_history import failure_text, is_running, load_history, run_action


class DailyPrompt:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.child: subprocess.Popen | None = None
        self.rows: dict[str, dict] = {}
        self.notice = ""
        root.title("MarketCouncil · 오늘 실행과 기록")
        root.geometry("980x660")
        root.minsize(860, 600)
        panel = ttk.Frame(root, padding=24)
        panel.pack(fill="both", expand=True)
        ttk.Label(panel, text="오늘의 MarketCouncil", font=("맑은 고딕", 22, "bold")).pack(anchor="w")
        ttk.Label(panel, text="실행 기록을 확인하고, 오늘 분석을 시작할지 선택하세요. 닫으면 새 분석을 시작하지 않습니다.").pack(anchor="w", pady=(8, 16))
        self.summary = ttk.Label(panel, font=("맑은 고딕", 11, "bold"))
        self.summary.pack(anchor="w", pady=(0, 12))
        table = ttk.Frame(panel)
        table.pack(fill="both", expand=True)
        self.table = ttk.Treeview(table, columns=("day", "company", "status"), show="headings", selectmode="browse", height=9)
        for name, title, width in (("day", "실행일 (한국 시간)", 145), ("company", "기업", 170), ("status", "상태", 460)):
            self.table.heading(name, text=title)
            self.table.column(name, width=width, minwidth=120, stretch=name == "status")
        scrollbar = ttk.Scrollbar(table, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.table.pack(fill="both", expand=True)
        self.table.bind("<<TreeviewSelect>>", self.show_details)
        ttk.Label(panel, text="선택한 날짜 · 실행 상태와 오류 이유").pack(anchor="w", pady=(14, 4))
        self.details = ScrolledText(panel, height=7, wrap="word", font=("맑은 고딕", 10), relief="flat", background="#f4f5f7", padx=12, pady=8)
        self.details.pack(fill="x")
        self.details.configure(state="disabled")
        ttk.Label(panel, text="실행을 선택하면 OpenAI 사용료가 발생하며 분석 결과와 근거가 공식 공개됩니다.").pack(anchor="w", pady=(12, 4))
        buttons = ttk.Frame(panel)
        buttons.pack(fill="x", pady=(8, 0))
        self.run_button = ttk.Button(buttons, command=self.start)
        self.run_button.pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="새로고침", command=self.refresh).pack(side="left")
        ttk.Button(buttons, text="운영자 설정", command=self.setup).pack(side="left", padx=8)
        self.close_button = ttk.Button(buttons, text="지금은 안 함", command=root.destroy)
        self.close_button.pack(side="right")
        self.refresh()
        root.after(1500, self.poll)

    def refresh(self) -> None:
        day = daily.today()
        running = self.child is not None and self.child.poll() is None or is_running(daily.DATA)
        rows, warnings = load_history(daily.DATA, day, running)
        selected = self.table.selection()
        selected_day = selected[0] if selected else day
        self.rows = {row["day"]: row for row in rows}
        for row in rows:
            values = (row["day"], row.get("company") or "—", row["label"])
            if self.table.exists(row["day"]):
                self.table.item(row["day"], values=values)
            else:
                self.table.insert("", "end", iid=row["day"], values=values)
        self.table.set_children("", *(row["day"] for row in rows))
        self.table.selection_set(selected_day if selected_day in self.rows else day)
        label, enabled = run_action(self.rows[day], running, (daily.DATA / "credentials.dpapi").exists())
        if any(warning.startswith("state.json ·") for warning in warnings):
            enabled = False
        self.run_button.configure(text=label, state="normal" if enabled else "disabled")
        self.close_button.configure(text="창 닫기 (실행은 계속)" if running else "지금은 안 함")
        self.summary.configure(text=f"오늘 {day}  ·  {self.rows[day]['label']}" + ("  ·  다른 날짜의 작업이 진행 중입니다." if running and "실행 중" not in self.rows[day]["label"] and self.rows[day]["status"] != "completed" else ""))
        self.notice = "\n".join(warnings)
        self.show_details()

    def show_details(self, event: object = None) -> None:
        selected = self.table.selection()
        if not selected or selected[0] not in self.rows:
            return
        row = self.rows[selected[0]]
        parts = [row["day"] + " · " + row["label"]]
        if row.get("analysis_attempts"):
            parts.append(f"당일 분석 시도 {row['analysis_attempts']} / 2회")
        if row["day"] != daily.today():
            parts.append("과거 기록은 열람용입니다. 실행 버튼은 오늘 작업에만 적용됩니다.")
        errors = row.get("errors", [])
        if row["status"] == "completed" and errors:
            parts.append("아래는 이전 실패 또는 종료 정리 기록입니다. 최종 상태는 공식 게시 완료입니다.")
        parts.extend(failure_text(error) for error in errors)
        if not errors:
            parts.append("저장된 오류 기록이 없습니다.")
        if row["status"] == "checkpoint":
            parts.append("이 날짜에는 중간 저장 파일이 있습니다. 기존 기록만으로 공식 게시 성공 여부를 판단하지 않습니다.")
        if self.notice:
            parts.append(self.notice)
        self.details.configure(state="normal")
        text = "\n\n".join(parts)
        if self.details.get("1.0", "end-1c") != text:
            self.details.delete("1.0", "end")
            self.details.insert("1.0", text)
        self.details.configure(state="disabled")

    def start(self) -> None:
        self.refresh()
        if str(self.run_button["state"]) == "disabled":
            return
        try:
            self.child = subprocess.Popen(daily.launch_command(), cwd=daily.runtime_root(), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except OSError:
            messagebox.showerror("실행 실패", "실행 프로그램 경로와 Python 설치 상태를 확인하세요.", parent=self.root)
        self.refresh()

    def setup(self) -> None:
        if self.child is not None and self.child.poll() is None or is_running(daily.DATA):
            messagebox.showinfo("작업 실행 중", "작업이 끝난 뒤 설정을 변경하세요.", parent=self.root)
            return
        try:
            subprocess.Popen(daily.launch_command(setup=True), cwd=daily.runtime_root(), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.root.destroy()
        except OSError:
            messagebox.showerror("설정 실패", "설정 프로그램을 열 수 없습니다. 실행 경로를 확인하세요.", parent=self.root)

    def poll(self) -> None:
        self.refresh()
        self.root.after(1500, self.poll)


def prompt() -> None:
    root = tk.Tk()
    DailyPrompt(root)
    root.mainloop()


if __name__ == "__main__":
    prompt()
