"""Ask before a paid daily run; closing this window never starts analysis."""
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, font as tkfont
from tkinter.scrolledtext import ScrolledText

from desktop import daily_official as daily
from desktop.daily_history import failure_text, is_running, load_history, run_action


# Same surface and accent colors as the public research library.
PAGE = "#fafafa"
PAPER = "#ffffff"
TINT = "#f0f3fa"
INK = "#171717"
MUTED = "#737373"
ACCENT = "#2455e6"


class DailyPrompt:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.child: subprocess.Popen | None = None
        self.rows: dict[str, dict] = {}
        self.notice = ""
        root.title("MarketCouncil · 오늘 실행과 기록")
        root.geometry("1060x740")
        root.minsize(900, 660)
        root.configure(background=PAGE)
        families = tkfont.families(root)
        self.font = next((name for name in ("Noto Sans KR", "맑은 고딕", "Malgun Gothic") if name in families), "TkDefaultFont")
        self.style = ttk.Style(root)
        self.style.theme_use("clam")
        self.style.configure("MC.TFrame", background=PAGE)
        self.style.configure("Paper.MC.TFrame", background=PAPER)
        self.style.configure("Tint.MC.TFrame", background=TINT)
        self.style.configure("MC.TLabel", background=PAGE, foreground=INK, font=(self.font, 10))
        self.style.configure("Muted.MC.TLabel", foreground=MUTED)
        self.style.configure("Caption.MC.TLabel", foreground=MUTED, font=("Segoe UI", 8))
        self.style.configure("Title.MC.TLabel", font=(self.font, 22, "bold"))
        self.style.configure("Section.MC.TLabel", font=(self.font, 11, "bold"))
        self.style.configure("Paper.MC.TLabel", background=PAPER)
        self.style.configure("Tint.MC.TLabel", background=TINT, foreground=MUTED, font=(self.font, 9))
        self.style.configure("Value.MC.TLabel", background=TINT, font=(self.font, 14, "bold"), foreground=INK)
        self.style.configure("MC.TButton", font=(self.font, 9), padding=(16, 11), background=TINT, foreground=ACCENT, borderwidth=0, focusthickness=2, focuscolor=ACCENT)
        self.style.map("MC.TButton", background=[("disabled", "#f1f2f5"), ("active", "#e3eafa")], foreground=[("disabled", "#81899a")])
        self.style.configure("Primary.MC.TButton", background=ACCENT, foreground=PAPER, font=(self.font, 10, "bold"), padding=(22, 8), focuscolor=INK)
        self.style.map("Primary.MC.TButton", background=[("disabled", "#e8edf8"), ("active", "#1d45c1")], foreground=[("disabled", "#566a98")])
        self.style.configure("Quiet.MC.TButton", background=PAGE, foreground=MUTED)
        self.style.map("Quiet.MC.TButton", background=[("active", TINT)], foreground=[("active", ACCENT)])
        self.style.configure("MC.Treeview", font=(self.font, 10), background=PAPER, fieldbackground=PAPER, foreground=INK, rowheight=34, borderwidth=0, relief="flat")
        self.style.layout("MC.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        self.style.map("MC.Treeview", background=[("selected", "#edf2ff")], foreground=[("selected", "#244bb7")])
        self.style.configure("MC.Treeview.Heading", font=(self.font, 9), background=PAPER, foreground=MUTED, relief="flat", borderwidth=0, padding=(16, 8))
        self.style.map("MC.Treeview.Heading", background=[("active", PAPER)])
        self.style.configure("MC.Vertical.TScrollbar", background="#dce2ef", troughcolor=PAPER, borderwidth=0, arrowsize=12, relief="flat")

        header = ttk.Frame(root, style="Paper.MC.TFrame", padding=(32, 4))
        header.pack(fill="x")
        logo = tk.Canvas(header, width=36, height=36, background=PAPER, highlightthickness=0)
        logo.pack(side="left", padx=(0, 11))
        logo.create_polygon(7, 0, 29, 0, 36, 7, 36, 29, 29, 36, 7, 36, 0, 29, 0, 7, smooth=True, fill=ACCENT, outline="")
        logo.create_text(17, 17, text="M", fill=PAPER, font=("Segoe UI", 18, "bold"))
        logo.create_text(27, 26, text="c", fill=PAPER, font=("Segoe UI", 9))
        brand = ttk.Frame(header, style="Paper.MC.TFrame")
        brand.pack(side="left")
        ttk.Label(brand, text="MarketCouncil", style="Paper.MC.TLabel", font=("Segoe UI", 15, "bold")).pack(anchor="w")
        ttk.Label(brand, text="I N V E S T M E N T   R E S E A R C H", style="Paper.MC.TLabel", foreground=MUTED, font=("Segoe UI", 7)).pack(anchor="w", pady=(3, 0))
        ttk.Label(header, text="LOCAL WORKSPACE  /  내 PC", style="Paper.MC.TLabel", foreground=MUTED, font=(self.font, 9)).pack(side="right")

        panel = ttk.Frame(root, style="MC.TFrame", padding=(32, 12, 32, 18))
        panel.pack(fill="both", expand=True)
        footer = ttk.Frame(panel, style="MC.TFrame")
        footer.pack(side="bottom", fill="x")
        detail_panel = ttk.Frame(panel, style="MC.TFrame")
        detail_panel.pack(side="bottom", fill="x")
        ttk.Label(panel, text="DAILY RESEARCH", style="Caption.MC.TLabel").pack(anchor="w")
        ttk.Label(panel, text="오늘의 리서치", style="Title.MC.TLabel").pack(anchor="w", pady=(4, 4))
        ttk.Label(panel, text="지난 실행을 확인하고 오늘의 분석을 시작하세요. 창을 닫으면 새 분석을 실행하지 않습니다.", style="Muted.MC.TLabel").pack(anchor="w")

        overview = ttk.Frame(panel, style="Tint.MC.TFrame", padding=(22, 8))
        overview.pack(fill="x", pady=(12, 14))
        overview.columnconfigure((0, 1), weight=1, uniform="overview")
        overview.columnconfigure(2, weight=2, uniform="overview")
        for column, caption in enumerate(("오늘의 날짜 · 한국 시간", "분석 기업", "현재 상태")):
            ttk.Label(overview, text=caption, style="Tint.MC.TLabel").grid(row=0, column=column, sticky="w", padx=(0, 18), pady=(0, 6))
        self.summary_date = ttk.Label(overview, style="Value.MC.TLabel", font=("Segoe UI", 16))
        self.summary_date.grid(row=1, column=0, sticky="w")
        self.summary_company = ttk.Label(overview, style="Value.MC.TLabel")
        self.summary_company.grid(row=1, column=1, sticky="w")
        self.summary = ttk.Label(overview, style="Value.MC.TLabel", wraplength=430, font=(self.font, 12, "bold"), foreground=ACCENT)
        self.summary.grid(row=1, column=2, sticky="w")

        section = ttk.Frame(panel, style="MC.TFrame")
        section.pack(fill="x", pady=(0, 10))
        ttk.Label(section, text="기록된 실행", style="Section.MC.TLabel").pack(side="left")
        ttk.Label(section, text="최근 날짜순  ↓", style="Muted.MC.TLabel", font=(self.font, 8)).pack(side="right")
        table = ttk.Frame(panel, style="Paper.MC.TFrame", padding=(10, 0, 8, 8))
        table.pack(fill="both", expand=True)
        self.table = ttk.Treeview(table, columns=("day", "company", "status"), show="headings", selectmode="browse", height=3, style="MC.Treeview")
        for name, title, width in (("day", "실행일", 155), ("company", "기업", 170), ("status", "실행 상태", 550)):
            self.table.heading(name, text=title, anchor="w")
            self.table.column(name, width=width, minwidth=120, stretch=name == "status", anchor="w")
        self.table.tag_configure("failed", foreground="#954555")
        self.table.tag_configure("completed", foreground="#405b96")
        scrollbar = ttk.Scrollbar(table, orient="vertical", command=self.table.yview, style="MC.Vertical.TScrollbar")
        self.table.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.table.pack(fill="both", expand=True)
        self.table.bind("<<TreeviewSelect>>", self.show_details)
        ttk.Label(detail_panel, text="실행 상세", style="Section.MC.TLabel").pack(anchor="w", pady=(12, 8))
        self.details = ScrolledText(detail_panel, height=4, wrap="word", font=(self.font, 9), relief="flat", borderwidth=0, highlightthickness=1, highlightbackground=PAPER, highlightcolor=ACCENT, background=PAPER, foreground="#586174", selectbackground="#edf2ff", selectforeground=INK, padx=16, pady=12)
        self.details.pack(fill="x")
        self.details.configure(state="disabled")
        self.details.vbar.configure(background=PAPER, troughcolor=PAPER, activebackground=TINT, relief="flat", borderwidth=0, width=12)
        ttk.Label(footer, text="실행 시 OpenAI 사용료가 발생하며, 결과와 근거가 공식 공개됩니다.", style="Muted.MC.TLabel", font=(self.font, 8)).pack(anchor="w", pady=(14, 9))
        buttons = ttk.Frame(footer, style="MC.TFrame")
        buttons.pack(fill="x")
        self.run_button = ttk.Button(buttons, command=self.start, style="Primary.MC.TButton")
        self.run_button.pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="새로고침", command=self.refresh, style="Quiet.MC.TButton").pack(side="left")
        ttk.Button(buttons, text="운영자 설정", command=self.setup, style="Quiet.MC.TButton").pack(side="left", padx=4)
        self.close_button = ttk.Button(buttons, text="지금은 안 함", command=root.destroy, style="MC.TButton")
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
                self.table.item(row["day"], values=values, tags=(row["status"],))
            else:
                self.table.insert("", "end", iid=row["day"], values=values, tags=(row["status"],))
        self.table.set_children("", *(row["day"] for row in rows))
        self.table.selection_set(selected_day if selected_day in self.rows else day)
        label, enabled = run_action(self.rows[day], running, (daily.DATA / "credentials.dpapi").exists())
        if any(warning.startswith("state.json ·") for warning in warnings):
            enabled = False
        self.run_button.configure(text=label, state="normal" if enabled else "disabled")
        self.close_button.configure(text="창 닫기 (실행은 계속)" if running else "지금은 안 함")
        self.summary_date.configure(text=day.replace("-", "."))
        self.summary_company.configure(text=self.rows[day].get("company") or "실행 시 확인")
        other_day_running = running and "실행 중" not in self.rows[day]["label"] and self.rows[day]["status"] != "completed"
        self.summary.configure(text="다른 날짜의 작업 실행 중" if other_day_running else self.rows[day]["label"])
        self.notice = "\n".join(warnings)
        self.show_details()

    def show_details(self, event: object = None) -> None:
        selected = self.table.selection()
        if not selected or selected[0] not in self.rows:
            return
        row = self.rows[selected[0]]
        parts = [row["day"] + " · " + row["label"]]
        if row.get("analysis_attempts"):
            parts[0] += f" · 분석 시도 {row['analysis_attempts']} / 2회"
        errors = row.get("errors", [])
        if row["status"] == "completed" and errors:
            parts.append("아래는 이전 실패 또는 종료 정리 기록입니다. 최종 상태는 공식 게시 완료입니다.")
        parts.extend(failure_text(error) for error in reversed(errors))
        if not errors:
            parts.append("저장된 오류 기록이 없습니다.")
        if row["status"] == "checkpoint":
            parts.append("이 날짜에는 중간 저장 파일이 있습니다. 기존 기록만으로 공식 게시 성공 여부를 판단하지 않습니다.")
        if row["day"] != daily.today():
            parts.append("과거 기록은 열람용입니다. 실행 버튼은 오늘 작업에만 적용됩니다.")
        if self.notice:
            parts.append(self.notice)
        self.details.configure(state="normal")
        text = "\n".join(parts)
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
