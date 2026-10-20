"""User-scoped desktop API. No service-role or server secret is accepted."""
import errno
import json
import socket
import ssl
import time
from http.client import IncompleteRead
from urllib.parse import urlsplit, parse_qs
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from frontend.export_results import FIELDS, compact_evidence
from tools.result_validation import validate_result

BASE = "https://snembdnkylggbxtxfqyz.supabase.co"
PUBLIC_KEY = "sb_publishable_qJ8trycyiIECgCF5xHhcYg_JLHs8msL"
SITE = "https://frontend-six-pi-h5i7tztups.vercel.app/app"


class CloudAPIError(RuntimeError):
    """Keep only the HTTP status; provider bodies can contain private data."""
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"계정 연결에 실패했습니다 (HTTP {status_code}). 로그인 또는 권한을 확인하세요.")


class OfficialSchemaRequired(RuntimeError):
    """A safe, actionable setup failure that must stop before paid analysis."""


class CloudNetworkError(RuntimeError):
    """Keep transport metadata only; URLs and provider messages are private."""
    def __init__(self, kind: str, attempts: int, retry_allowed: bool,
                 error_number: int | None = None, windows_error: int | None = None) -> None:
        self.network_kind = kind
        self.attempts = attempts
        self.retry_allowed = retry_allowed
        self.errno = error_number
        self.winerror = windows_error
        super().__init__("네트워크 연결에 실패했습니다. 인터넷 연결을 확인한 뒤 다시 시도하세요.")


def _network_failure(error: BaseException, method: str, attempts: int) -> CloudNetworkError:
    reason = error.reason if isinstance(error, URLError) else error
    number = getattr(reason, "errno", None)
    windows_error = getattr(reason, "winerror", None)
    number = number if isinstance(number, int) and not isinstance(number, bool) else None
    windows_error = windows_error if isinstance(windows_error, int) and not isinstance(windows_error, bool) else None
    native_code = windows_error if windows_error is not None else number
    if isinstance(reason, socket.gaierror):
        kind = "dns"
        transient = number == socket.EAI_AGAIN
    elif isinstance(reason, TimeoutError) or native_code in (errno.ETIMEDOUT, 10060):
        kind, transient = "timeout", True
    elif isinstance(reason, ssl.SSLError):
        kind, transient = "tls", False
    elif isinstance(reason, IncompleteRead):
        kind, transient = "response_incomplete", True
    elif isinstance(reason, ConnectionRefusedError) or native_code in (errno.ECONNREFUSED, 10061):
        kind, transient = "connection_refused", True
    elif isinstance(reason, ConnectionResetError) or native_code in (errno.ECONNRESET, 10054):
        kind, transient = "connection_reset", True
    elif isinstance(reason, ConnectionAbortedError) or native_code in (errno.ECONNABORTED, 10053):
        kind, transient = "connection_aborted", True
    else:
        kind = "network"
        transient = native_code in (errno.ENETUNREACH, errno.EHOSTUNREACH, errno.EAGAIN, 10051, 10065)
    retry_allowed = transient and method in ("GET", "HEAD")
    return CloudNetworkError(kind, attempts, retry_allowed, number, windows_error)


def request(path: str, body: dict | None = None, token: str = "", method: str = "POST") -> object:
    headers = {"apikey": PUBLIC_KEY, "Content-Type": "application/json", "Prefer": "return=representation"}
    if token:
        headers["Authorization"] = "Bearer " + token
    method = method.upper()
    req = Request(BASE + path, data=json.dumps(body).encode() if body is not None else None, headers=headers, method=method)
    for attempt in range(1, 4):
        try:
            with urlopen(req, timeout=60) as response:
                raw = response.read()
                return json.loads(raw) if raw else None
        except HTTPError as error:
            raise CloudAPIError(error.code) from None
        except (OSError, IncompleteRead) as error:
            failure = _network_failure(error, method, attempt)
            # urllib may follow redirects, so even a connect error cannot prove a POST was unsent.
            if not failure.retry_allowed or attempt == 3:
                raise failure from None
            time.sleep(0.5 * attempt)


def send_login(email: str) -> None:
    request("/auth/v1/otp", {"email": email.strip(), "create_user": True, "gotrue_meta_security": {} })


def login_link(link: str) -> dict:
    parsed = urlsplit(link.strip())
    if parsed.scheme != "https" or parsed.hostname != urlsplit(BASE).hostname or parsed.path != "/auth/v1/verify":
        raise ValueError("이 프로젝트가 보낸 메일의 로그인 버튼 링크를 복사하세요.")
    params = parse_qs(parsed.query)
    token = params.get("token", [""])[0]
    kind = params.get("type", [""])[0]
    if not token or kind not in ("magiclink", "signup", "email"):
        raise ValueError("유효한 로그인 링크가 아닙니다. 새 메일을 요청하세요.")
    return request("/auth/v1/verify", {"token_hash": token, "type": kind})


def upload_result(data: dict, session: dict, identifier: str) -> dict:
    from datetime import datetime
    import uuid
    uuid.UUID(identifier)
    validate_result(data)
    payload = compact_evidence({key: data[key] for key in FIELDS if key in data})
    if len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) > 1900000:
        raise ValueError("결과 크기가 업로드 한도를 넘습니다. 더 작은 결과 파일을 선택하세요.")
    row = {"id": identifier, "user_id": session["user"]["id"], "company_name": payload["company_name"],
           "ticker": (payload.get("financial_data") or {}).get("ticker") or "",
           "analysis_date": payload.get("created_at") or datetime.now().isoformat(), "payload": payload}
    existing = request("/rest/v1/discussions?id=eq." + identifier + "&select=id", token=session["access_token"], method="GET")
    if existing:
        return existing[0]
    result = request("/rest/v1/discussions", row, session["access_token"])
    return result[0]


def official_day() -> str:
    from datetime import datetime, timezone, timedelta
    return datetime.now(timezone(timedelta(hours=9))).date().isoformat()


def official_selection(session: dict, day: str) -> list:
    # The join also ignores stale selections until the database migration is applied.
    return request("/rest/v1/daily_official_discussions?publication_date=eq." + day
                   + "&select=discussion_id,discussions!inner(visibility)&discussions.visibility=eq.public",
                   token=session["access_token"], method="GET")


def select_official(session: dict, identifier: str, day: str) -> str:
    return request("/rest/v1/rpc/select_daily_official",
                   {"discussion": identifier, "expected_day": day, "replace_existing": False},
                   session["access_token"])


def check_official_schema(session: dict, day: str) -> None:
    """Probe the new RPC with a null discussion, which can never publish a row."""
    try:
        request("/rest/v1/rpc/select_daily_official",
                {"discussion": None, "expected_day": day, "replace_existing": False},
                session["access_token"])
    except CloudAPIError as error:
        if error.status_code == 400:
            return  # The matching RPC rejects the deliberately absent discussion.
        if error.status_code == 404:
            raise OfficialSchemaRequired("공식 게시 DB 마이그레이션이 필요합니다. 설정 적용 전에는 유료 분석을 시작하지 않습니다.") from None
        raise
    raise RuntimeError("공식 게시 설정을 안전하게 확인하지 못했습니다. 운영자에게 문의하세요.")


def prepare_official(session: dict, discussion_id: str | None = None) -> dict:
    """Check operator access and today's selection before any paid analysis."""
    if session.get("refresh_token"):
        session = request("/auth/v1/token?grant_type=refresh_token", {"refresh_token": session["refresh_token"]})
    if request("/rest/v1/rpc/is_official_editor", {}, session["access_token"]) is not True:
        raise ValueError("공식 운영자 계정으로 이메일 계정 연결을 먼저 진행하세요.")
    day = official_day()
    rows = official_selection(session, day)
    if rows and any(row["discussion_id"] != discussion_id for row in rows):
        raise ValueError("오늘 공식 토론이 이미 게시되어 있습니다. 새 분석을 시작하지 않습니다.")
    check_official_schema(session, day)
    return session


def publish_official(data: dict, session: dict) -> str:
    import hashlib
    import uuid
    if data.get("company_name") != "삼성전자" or data.get("financial_data", {}).get("ticker") != "005930.KS":
        raise ValueError("삼성전자(005930.KS) 분석 결과만 공식 게시할 수 있습니다.")
    day = official_day()
    identifier = str(uuid.uuid5(uuid.NAMESPACE_URL, session["user"]["id"] + hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()))
    session = prepare_official(session, identifier)
    upload_result(data, session, identifier)
    return select_official(session, identifier, day)
