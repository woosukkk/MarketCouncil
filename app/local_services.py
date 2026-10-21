import csv
import json
import os
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator
from urllib.error import URLError
from urllib.request import urlopen


PROJECT_ROOT = Path(__file__).resolve().parent.parent
COMPOSE_FILE = PROJECT_ROOT / "infra" / "searxng" / "docker-compose.yml"
DOCKER_DESKTOP = Path(
    os.environ.get(
        "PROGRAMFILES",
        r"C:\Program Files",
    )
) / "Docker" / "Docker" / "Docker Desktop.exe"
SEARXNG_URL = os.getenv("SEARXNG_URL", "http://127.0.0.1:8080/")
HIDDEN_PROCESS = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}


def ensure_local_services() -> None:
    if _service_ready():
        print("[오픈소스 서비스] SearXNG 준비 완료")
        return

    if os.getenv("MANAGE_LOCAL_SERVICES", "true").lower() == "false":
        _wait_until(_service_ready, 60, "SearXNG")
        return

    if not COMPOSE_FILE.exists():
        raise RuntimeError(f"Docker Compose 설정이 없습니다: {COMPOSE_FILE}")

    if not _docker_ready():
        _start_docker_desktop()
        _wait_until(_docker_ready, 120, "Docker 엔진")

    print("[오픈소스 서비스] SearXNG 컨테이너 시작")
    try:
        result = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                str(COMPOSE_FILE),
                "up",
                "-d",
            ],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            **HIDDEN_PROCESS,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        detail = getattr(error, "stderr", "") or str(error)
        raise RuntimeError(
            f"SearXNG 컨테이너를 시작하지 못했습니다: {detail.strip()}"
        ) from error

    if result.stdout.strip():
        print(result.stdout.strip())
    _wait_until(_service_ready, 60, "SearXNG 검색 API")
    print("[오픈소스 서비스] SearXNG 준비 완료")


@contextmanager
def daily_local_services(
    on_cleanup_error: Callable[[str], None] | None = None,
) -> Iterator[None]:
    """Release only services this daily run started, including failed runs."""
    if (os.getenv("MANAGE_LOCAL_SERVICES", "true").lower() == "false"
            or _service_ready()):
        ensure_local_services()
        yield
        return

    def cleanup(command: list[str], label: str) -> None:
        if _cleanup_command(command, label) or on_cleanup_error is None:
            return
        try:
            on_cleanup_error(label)
        except Exception:
            print("[오픈소스 서비스] 자동 종료 오류 기록 실패")

    desktop_started = False
    before: set[str] | None = None
    try:
        if not COMPOSE_FILE.exists():
            raise RuntimeError(f"Docker Compose 설정이 없습니다: {COMPOSE_FILE}")
        if not _docker_ready():
            desktop_started = _desktop_stopped()
            if desktop_started:
                # A failed start can still auto-resume this project before returning.
                before = set()
            _start_docker_desktop()
            _wait_until(_docker_ready, 120, "Docker 엔진")
        if before is None:
            before = _running_container_ids(compose_only=True)
        ensure_local_services()
        yield
    finally:
        if before is not None:
            after = _running_container_ids(compose_only=True)
            if after is not None:
                for container_id in sorted(after - before):
                    cleanup(["docker", "stop", "--time", "10", container_id], "SearXNG")
        if desktop_started and _running_container_ids() == set():
            cleanup(["docker", "desktop", "stop", "--timeout", "30"], "Docker Desktop")


def _running_container_ids(*, compose_only: bool = False) -> set[str] | None:
    command = (["docker", "compose", "-f", str(COMPOSE_FILE),
                "ps", "--status", "running", "-q", "searxng"]
               if compose_only else ["docker", "ps", "-q"])
    try:
        result = subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True,
                                text=True, encoding="utf-8", errors="replace",
                                timeout=15, check=False, **HIDDEN_PROCESS)
        if result.returncode != 0:
            return None
        ids = set(result.stdout.split())
        # Unknown output must never become a target for a stop command.
        if any(len(item) not in (12, 64) or any(c not in "0123456789abcdef" for c in item)
               for item in ids):
            return None
        return ids
    except (OSError, subprocess.TimeoutExpired):
        return None


def _desktop_stopped() -> bool:
    if os.name != "nt":
        return False
    try:
        result = subprocess.run(["docker", "desktop", "status", "--format", "json"],
                                capture_output=True, text=True, encoding="utf-8", errors="replace",
                                timeout=15, check=False, **HIDDEN_PROCESS)
        if result.returncode != 0:
            return _desktop_processes_stopped()
        return json.loads(result.stdout).get("Status") == "stopped"
    except (OSError, subprocess.TimeoutExpired):
        return _desktop_processes_stopped()
    except (ValueError, AttributeError):
        return False


def _desktop_processes_stopped() -> bool:
    # Desktop's CLI has no status endpoint after shutdown; verify processes instead.
    try:
        result = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True,
                                text=True, errors="replace", timeout=15,
                                check=False, **HIDDEN_PROCESS)
        if result.returncode != 0:
            return False
        rows = list(csv.reader(result.stdout.splitlines(), strict=True))
        if not rows or any(len(row) != 5 or not row[1].isdigit() for row in rows):
            return False
        docker_processes = {"docker desktop.exe", "com.docker.backend.exe"}
        return not any(row[0].casefold() in docker_processes for row in rows)
    except (OSError, subprocess.TimeoutExpired, csv.Error, UnicodeError):
        return False


def _cleanup_command(command: list[str], label: str) -> bool:
    try:
        result = subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True,
                                text=True, encoding="utf-8", errors="replace",
                                timeout=40, check=False, **HIDDEN_PROCESS)
        if result.returncode == 0:
            print(f"[오픈소스 서비스] {label} 자동 종료 완료")
            return True
    except (OSError, subprocess.TimeoutExpired):
        pass
    print(f"[오픈소스 서비스] {label} 자동 종료 실패: 기존 실행 상태를 유지합니다.")
    return False


def _docker_ready() -> bool:
    try:
        return subprocess.run(
            ["docker", "info"],
            check=False,
            capture_output=True,
            timeout=10,
            **HIDDEN_PROCESS,
        ).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _start_docker_desktop() -> None:
    if os.name != "nt":
        raise RuntimeError("Docker 엔진을 먼저 실행하세요.")
    if not DOCKER_DESKTOP.exists():
        raise RuntimeError(
            f"Docker Desktop 실행 파일이 없습니다: {DOCKER_DESKTOP}"
        )
    print("[오픈소스 서비스] Docker Desktop 시작")
    try:
        subprocess.run(
            ["docker", "desktop", "start", "--detach", "--timeout", "30"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=40,
            **HIDDEN_PROCESS,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise RuntimeError("Docker Desktop을 시작하지 못했습니다.") from error


def _service_ready() -> bool:
    try:
        with urlopen(SEARXNG_URL, timeout=2) as response:
            return response.status == 200
    except (OSError, URLError):
        return False


def _wait_until(
    check: Callable[[], bool],
    timeout_seconds: int,
    label: str,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(2)
    raise RuntimeError(f"{label}이 {timeout_seconds}초 안에 준비되지 않았습니다.")
