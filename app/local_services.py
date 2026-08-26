import os
import subprocess
import time
from pathlib import Path
from typing import Callable
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
SEARXNG_URL = "http://127.0.0.1:8080/"


def ensure_local_services() -> None:
    if _service_ready():
        print("[오픈소스 서비스] SearXNG 준비 완료")
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
        )
    except (OSError, subprocess.CalledProcessError) as error:
        detail = getattr(error, "stderr", "") or str(error)
        raise RuntimeError(
            f"SearXNG 컨테이너를 시작하지 못했습니다: {detail.strip()}"
        ) from error

    if result.stdout.strip():
        print(result.stdout.strip())
    _wait_until(_service_ready, 60, "SearXNG 검색 API")
    print("[오픈소스 서비스] SearXNG 준비 완료")


def _docker_ready() -> bool:
    try:
        return subprocess.run(
            ["docker", "info"],
            check=False,
            capture_output=True,
            timeout=10,
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
        subprocess.Popen([str(DOCKER_DESKTOP)])
    except OSError as error:
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
