import os
import subprocess
import sys
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from threading import Lock

from tools.financial_data import TICKER_MAP


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run_analysis(company_name: str) -> Path:
    """Run the existing CLI without importing its models into the web server."""
    if company_name not in TICKER_MAP:
        raise ValueError("지원하는 기업을 선택하세요.")
    try:
        result = subprocess.run(
            [sys.executable, "-u", "-m", "app.debate_main"],
            input=f"{company_name}\n",
            cwd=PROJECT_ROOT,
            env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3600,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("분석이 60분을 초과하여 종료되었습니다. 로컬 서비스와 API 상태를 확인하세요.") from error
    except OSError as error:
        raise RuntimeError(f"분석 프로세스를 시작하지 못했습니다: {error}") from error
    if result.returncode:
        detail = (result.stdout + "\n" + result.stderr).strip()[-3000:]
        raise RuntimeError(detail or f"분석 프로세스 종료 코드: {result.returncode}")
    prefix = "토론 원본 JSON: "
    path_text = next((line.removeprefix(prefix).strip() for line in result.stdout.splitlines()
                      if line.startswith(prefix)), "")
    if not path_text:
        raise RuntimeError("분석은 종료되었지만 저장된 결과 경로를 확인하지 못했습니다.")
    path = (PROJECT_ROOT / path_text).resolve()
    if not path.is_relative_to(PROJECT_ROOT / "results" / "analysis_debate") or not path.is_file():
        raise RuntimeError("분석 결과 파일을 확인하지 못했습니다.")
    return path.relative_to(PROJECT_ROOT)


class AnalysisRunner:
    """One local analysis at a time, shared across browser sessions."""

    def __init__(self) -> None:
        # ponytail: one process per web server; use a job queue for multi-server deployment.
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._lock = Lock()
        self._future: Future[Path] | None = None
        self._company = ""

    def start(self, company_name: str) -> None:
        if company_name not in TICKER_MAP:
            raise ValueError("지원하는 기업을 선택하세요.")
        with self._lock:
            if self._future is not None and not self._future.done():
                raise RuntimeError("이미 분석이 실행 중입니다. 완료 후 다시 실행하세요.")
            self._future = self._executor.submit(run_analysis, company_name)
            self._company = company_name

    def current(self) -> tuple[str, Future[Path] | None]:
        with self._lock:
            return self._company, self._future
