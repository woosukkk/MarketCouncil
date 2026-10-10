"""User-scoped desktop API. No service-role or server secret is accepted."""
import json
from urllib.parse import urlsplit, parse_qs
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from frontend.export_results import FIELDS, compact_evidence

BASE = "https://snembdnkylggbxtxfqyz.supabase.co"
PUBLIC_KEY = "sb_publishable_qJ8trycyiIECgCF5xHhcYg_JLHs8msL"
SITE = "https://frontend-six-pi-h5i7tztups.vercel.app/app"


def request(path: str, body: dict | None = None, token: str = "", method: str = "POST") -> object:
    headers = {"apikey": PUBLIC_KEY, "Content-Type": "application/json", "Prefer": "return=representation"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = Request(BASE + path, data=json.dumps(body).encode() if body is not None else None, headers=headers, method=method)
    try:
        with urlopen(req, timeout=60) as response:
            raw = response.read()
            return json.loads(raw) if raw else None
    except HTTPError as error:
        raise RuntimeError(f"계정 연결에 실패했습니다 (HTTP {error.code}). 로그인 또는 권한을 확인하세요.") from None
    except (URLError, TimeoutError):
        raise RuntimeError("네트워크 연결을 확인하고 다시 시도하세요.") from None


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
    payload = compact_evidence({key: data[key] for key in FIELDS if key in data})
    row = {"id": identifier, "user_id": session["user"]["id"], "company_name": data["company_name"],
           "ticker": data.get("financial_data", {}).get("ticker", ""),
           "analysis_date": data.get("created_at", datetime.now().isoformat()), "payload": payload}
    existing = request("/rest/v1/discussions?id=eq." + identifier + "&select=id", token=session["access_token"], method="GET")
    if existing:
        return existing[0]
    result = request("/rest/v1/discussions", row, session["access_token"])
    return result[0]


def prepare_official(session: dict) -> dict:
    """Check operator access and today's selection before any paid analysis."""
    from datetime import datetime, timezone, timedelta
    if session.get("refresh_token"):
        session = request("/auth/v1/token?grant_type=refresh_token", {"refresh_token": session["refresh_token"]})
    if request("/rest/v1/rpc/is_official_editor", {}, session["access_token"]) is not True:
        raise ValueError("공식 운영자 계정으로 이메일 계정 연결을 먼저 진행하세요.")
    day = datetime.now(timezone(timedelta(hours=9))).date().isoformat()
    rows = request("/rest/v1/daily_official_discussions?publication_date=eq." + day + "&select=discussion_id", token=session["access_token"], method="GET")
    if rows:
        raise ValueError("오늘 공식 토론이 이미 게시되어 있습니다. 새 분석을 시작하지 않습니다.")
    return session


def publish_official(data: dict, session: dict) -> str:
    import hashlib
    import uuid
    if data.get("company_name") != "삼성전자" or data.get("financial_data", {}).get("ticker") != "005930.KS":
        raise ValueError("삼성전자(005930.KS) 분석 결과만 공식 게시할 수 있습니다.")
    session = prepare_official(session)
    identifier = str(uuid.uuid5(uuid.NAMESPACE_URL, session["user"]["id"] + hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()))
    upload_result(data, session, identifier)
    # shortcut: concurrent operators can replace a daily selection; add an insert-only RPC if multiple operators run this flow.
    return request("/rest/v1/rpc/select_daily_official", {"discussion": identifier}, session["access_token"])
