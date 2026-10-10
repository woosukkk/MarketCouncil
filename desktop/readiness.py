"""Read-only readiness checks; never transmit API keys or start analysis."""
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen

STAGES = (
    ("[공통 근거 수집 시작]", "자료 수집 · 재무 정보와 인용 근거를 찾고 있습니다."),
    ("[공통 근거 수집 완료]", "자료 정리 · 수집한 근거를 대조하고 있습니다."),
    ("[상승 관점 최초 분석 시작]", "상승 관점 분석 · 긍정 가설을 검토하고 있습니다."),
    ("[하락 관점 최초 분석 시작]", "하락 관점 분석 · 반대 근거와 위험을 검토하고 있습니다."),
    ("[중재자 토론 의제 선정 시작]", "토론 준비 · 비교할 핵심 쟁점을 정하고 있습니다."),
    ("[중재자 토론 최종 정리 시작]", "최종 정리 · 합의와 남은 쟁점을 정리하고 있습니다."),
    ("[중재자 토론 최종 정리 완료]", "결과 정리 · 근거와 탐색 안내를 구성하고 있습니다."),
)


def stage_for_line(line: str) -> str | None:
    for marker, description in STAGES:
        if marker in line:
            return description
    match = re.search(r"\[토론 (\d+)라운드 (상승 관점 발언|하락 관점 반론) 시작\]", line)
    if match:
        return f"토론 {match[1]}라운드 · {match[2]}을 진행하고 있습니다."
    if re.search(r"\[중재자 \d+라운드 검토 시작\]", line):
        return "토론 검토 · 양측의 주장과 근거를 비교하고 있습니다."
    return None


def check_readiness(key: str, search: str, data: Path) -> list[tuple[str, str]]:
    statuses = [("OpenAI 키", "입력됨 · 유효성은 실제 분석 시 확인합니다." if key.strip() else "입력 필요 · 기업 분석 탭에 본인 API 키를 입력하세요.")]
    parsed = urlsplit(search.strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        statuses.append(("검색 연결", "주소 확인 필요 · 로그인 정보 없는 http/https 주소를 입력하세요."))
        search_ready = False
    else:
        try:
            with urlopen(search.strip(), timeout=3) as response:
                search_ready = response.status == 200
        except Exception:
            search_ready = False
        statuses.append(("검색 연결", "응답 확인 · 검색 API 작동 여부는 분석 시 확인합니다." if search_ready else "연결 대기 · Docker Desktop을 실행하세요. 분석 시작 시 검색 서비스를 준비합니다."))
    if shutil.which("docker"):
        try:
            result = subprocess.run(["docker", "info"], capture_output=True, timeout=10,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            docker_ready = result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            docker_ready = False
        statuses.append(("Docker", "실행 중" if docker_ready else "시작 필요 · Docker Desktop을 열고 준비될 때까지 기다리세요."))
    else:
        statuses.append(("Docker", "설치 필요 · 외부 검색 서비스를 사용한다면 로컬 Docker 없이도 가능합니다." if search_ready else "설치 필요 · Docker Desktop을 설치한 뒤 프로그램을 다시 실행하세요."))
    statuses.append(("자료 수집 브라우저", "설치 기록 있음 · 실제 실행은 분석 시 확인합니다." if (data / "browser-ready").exists() else "첫 분석에서 자동 다운로드 · 인터넷 연결과 저장 공간이 필요합니다."))
    return statuses
