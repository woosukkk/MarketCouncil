"""Fetch dated earnings documents from each issuer's explicit official IR allowlist."""
import calendar
import hashlib
import ipaddress
import json
import re
import socket
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup
from pypdf.errors import PyPdfError

from tools.company_evidence_collector import extract_official_text
from tools.company_profiles import get_profile
from tools.evidence_dates import parse_evidence_date


MAX_BYTES = 25 * 1024 * 1024
MAX_FETCHES = 12
MAX_REDIRECTS = 3
TIMEOUT = (5, 20)
_KST = timezone(timedelta(hours=9))
_MONTH = r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
_EN_DATE = re.compile(rf"\b({_MONTH})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?\s*,?\s*(20\d{{2}})\b", re.I)
_MONTHS = {name.casefold(): number for number, name in enumerate(("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}
_RESULT = re.compile(r"earnings|financial\s+results|quarter.{0,20}results|실적|경영성과|business.results", re.I)
_ANNOUNCEMENT = re.compile(r"(?:will|to)\s+(?:announce|report|release)|(?:earnings|results?).{0,15}(?:release|announcement)\s+date|conference\s+call.{0,20}(?:access|details)|earnings\s+guidance|발표\s*(?:일정|예정|안내)|실적\s*예고", re.I)


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _date_value(value: object) -> date | None:
    parsed = parse_evidence_date(value)
    if parsed:
        return parsed
    if not isinstance(value, str):
        return None
    match = _EN_DATE.search(value)
    if match:
        try:
            return date(int(match[3]), _MONTHS[match[1][:3].casefold()], int(match[2]))
        except ValueError:
            return None
    match = re.search(r"\b(20\d{2})[년./-]\s*(\d{1,2})[월./-]\s*(\d{1,2})\s*일?", value)
    if match:
        try:
            return date(*map(int, match.groups()))
        except ValueError:
            pass
    return None


def _period(text: str, profile: dict[str, Any]) -> date | None:
    normalized = re.sub(r"\s+", " ", text)
    explicit = re.search(r"(?:quarter|three months|six months|period|year)\s+ended\s+([^;:]{0,50})", normalized, re.I)
    if explicit:
        parsed = _date_value(explicit[1])
        if parsed:
            return parsed
    if profile["market"] != "kr":
        return None  # Fiscal Q1 is not necessarily the calendar's March quarter.
    patterns = (
        (r"\b(20\d{2})\s*(?:년\s*|[. /-]\s*)?(?:Q\s*)?([1-4])\s*(?:Q|분기)\b", False),
        (r"\b(20\d{2})\s*Q\s*([1-4])\b", False),
        (r"\b([1-4])\s*Q\s*['’]?(20\d{2}|\d{2})\b", True),
    )
    for pattern, reverse in patterns:
        match = re.search(pattern, normalized, re.I)
        if match:
            year, quarter = (int(match[2]), int(match[1])) if reverse else tuple(map(int, match.groups()))
            if year < 100:
                year += 2000
            month = quarter * 3
            return date(year, month, calendar.monthrange(year, month)[1])
    return None


def _published(soup: BeautifulSoup | None, text: str, period: date) -> date | None:
    if soup is not None:
        for node in soup.find_all("meta"):
            name = str(node.get("property") or node.get("name") or node.get("itemprop") or "").casefold()
            if name in {"article:published_time", "og:published_time", "datepublished", "pubdate", "publish-date", "dc.date.issued", "date"}:
                parsed = _date_value(node.get("content"))
                if parsed:
                    return parsed
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            raw = script.string or script.get_text()
            if len(raw) > 500_000:
                continue
            try:
                data = json.loads(raw)
                nodes = data if isinstance(data, list) else [data]
                for node in nodes[:100]:
                    if not isinstance(node, dict):
                        continue
                    nested = node.get("@graph", [])
                    for candidate in [node, *(nested[:100] if isinstance(nested, list) else [])]:
                        if isinstance(candidate, dict):
                            parsed = _date_value(candidate.get("datePublished"))
                            if parsed:
                                return parsed
            except (ValueError, RecursionError, TypeError):
                continue
        for node in soup.find_all("time")[:10]:
            parsed = _date_value(node.get("datetime") or node.get_text(" ", strip=True))
            if parsed:
                return parsed
    for line in text[:2000].splitlines():
        if len(line) > 800:
            line = line[:800]
        for match in _EN_DATE.finditer(line):
            before = line[max(0, match.start() - 35):match.start()]
            if re.search(r"ended\s*$", before, re.I):
                continue
            parsed = _date_value(match[0])
            if parsed and parsed != period and (match.start() < 100 or re.search(r"announced|reported|발표", before, re.I)):
                return parsed
        if re.match(r"\s*20\d{2}[년./-]", line):
            parsed = _date_value(line)
            if parsed and parsed != period and not re.search(r"기준|종료|ended", line, re.I):
                return parsed
    return None


def _fiscal_tag(text: str) -> tuple[int, int] | None:
    match = re.search(r"\bFY[\s-]*['’]?(20\d{2}|\d{2})\s*[-/]?\s*Q\s*([1-4])\b", text, re.I)
    if match:
        year, quarter = map(int, match.groups())
        return (year + 2000 if year < 100 else year, quarter)
    return None


def _candidate_hint(url: str, label: str, profile: dict[str, Any], required: bool = False) -> dict[str, Any]:
    # Link hints rank failures only; they never supply a document's accepted dates.
    path = unquote(urlsplit(url).path)
    text = label + " " + re.sub(r"[_/-]+", " ", path)
    period = _period(text, profile)
    if period is None and profile["market"] == "kr":
        match = re.search(r"\bQ([1-4])\s+(20\d{2})\b", text, re.I)
        if not match:
            word = re.search(r"\b(first|second|third|fourth)\s+quarter\s+(20\d{2})\b", text, re.I)
            if word:
                quarter, year = ("first", "second", "third", "fourth").index(word[1].casefold()) + 1, int(word[2])
                month = quarter * 3
                period = date(year, month, calendar.monthrange(year, month)[1])
        else:
            quarter, year = map(int, match.groups())
            month = quarter * 3
            period = date(year, month, calendar.monthrange(year, month)[1])
    month = re.search(r"/(20\d{2})/(0[1-9]|1[0-2])(?:/|$)", path)
    specific = bool(re.search(r"press.release|business.results|financial\s+results|quarter.{0,20}results|earnings\s+release|실적", label + " " + path, re.I))
    return {"url": url, "required": required, "specific": specific, "period": period,
            "published": _date_value(label), "month": tuple(map(int, month.groups())) if month else None,
            "fiscal": _fiscal_tag(text)}


def _newer_candidate_uncovered(hint: dict[str, Any], documents: list[dict[str, Any]], profile: dict[str, Any]) -> bool:
    if not hint["required"] and not hint["specific"]:
        return False
    if any(document["source_url"] == hint["url"] for document in documents):
        return False
    today = datetime.now(_KST).date()
    if hint["period"]:
        if not hint["required"] and hint["period"] > today:
            return False
        return not any(date.fromisoformat(document["report_date"]) >= hint["period"] for document in documents)
    if hint["fiscal"]:
        return not any((tag := _fiscal_tag(document["source_url"] + " " + document["content"][:2000])) and tag >= hint["fiscal"] for document in documents)
    if hint["published"]:
        if not hint["required"] and hint["published"] > today:
            return False
        return not any(date.fromisoformat(document["published_at"]) >= hint["published"] for document in documents)
    if hint["month"]:
        if not hint["required"] and hint["month"] > (today.year, today.month):
            return False
        return not any((day.year, day.month) >= hint["month"] for document in documents if (day := date.fromisoformat(document["published_at"])))
    return hint["required"]


class OfficialIRCollector:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir.resolve()
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "MarketCouncil/1.0 official-evidence",
                                     "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                                     "Accept-Language": "en-US,en;q=0.9"})
        self._candidate_hints: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _url(value: str, profile: dict[str, Any]) -> str:
        if not isinstance(value, str) or len(value) > 2000:
            raise ValueError("invalid_source_url")
        parsed = urlsplit(value)
        path = unquote(parsed.path)
        if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443) or not parsed.hostname:
            raise ValueError("unverified_source_url")
        if any(part in (".", "..") for part in path.split("/")) or "\\" in path:
            raise ValueError("unverified_source_url")
        if not any(parsed.hostname == source["host"] and any(path.casefold().startswith(prefix.casefold()) for prefix in source["path_prefixes"]) for source in profile["ir_sources"]):
            raise ValueError("unverified_source_url")
        return urlunsplit(("https", parsed.hostname, parsed.path, parsed.query, ""))

    @staticmethod
    def _index(url: str, profile: dict[str, Any]) -> bool:
        def path(value: str) -> str:
            value = urlsplit(value).path.rstrip("/").casefold()
            return re.sub(r"/(?:default|index)(?:\.aspx?|\.html?)?$", "", value)
        return any(not source.get("is_document") and urlsplit(url).hostname == source["host"] and path(url) == path(source["url"]) for source in profile["ir_sources"])

    def _fetch(self, url: str, profile: dict[str, Any]) -> tuple[str, bytes, str]:
        for hop in range(MAX_REDIRECTS + 1):
            url = self._url(url, profile)
            try:
                addresses = socket.getaddrinfo(urlsplit(url).hostname, 443, type=socket.SOCK_STREAM)
                if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
                    raise ValueError("non_public_source_address")
                response = self.session.get(url, stream=True, allow_redirects=False, timeout=TIMEOUT)
                try:
                    if response.status_code in (301, 302, 303, 307, 308):
                        location = response.headers.get("Location")
                        if not location or hop == MAX_REDIRECTS:
                            raise ValueError("redirect_limit_exceeded")
                        url = self._url(urljoin(url, location), profile)
                        continue
                    if response.status_code != 200:
                        raise ValueError("http_" + str(response.status_code))
                    length = response.headers.get("Content-Length")
                    if length and (not length.isdigit() or int(length) > MAX_BYTES):
                        raise ValueError("source_size_limit_exceeded")
                    body = bytearray()
                    for chunk in response.iter_content(chunk_size=65536):
                        body.extend(chunk)
                        if len(body) > MAX_BYTES:
                            raise ValueError("source_size_limit_exceeded")
                    raw = bytes(body)
                    kind = ".pdf" if raw.startswith(b"%PDF") else ".html"
                    if not raw or (kind == ".html" and b"<" not in raw[:300]):
                        raise ValueError("unsupported_source_body")
                    return url, raw, kind
                finally:
                    response.close()
            except (requests.RequestException, OSError) as error:
                raise ValueError("source_unavailable") from error
        raise ValueError("redirect_limit_exceeded")

    def _links(self, url: str, body: bytes, profile: dict[str, Any]) -> list[str]:
        soup = BeautifulSoup(body, "html.parser")
        scored = []
        for anchor in soup.find_all("a", href=True)[:1000]:
            try:
                target = self._url(urljoin(url, anchor["href"]), profile)
                if self._index(target, profile):
                    continue
                row = anchor.find_parent(["tr", "li", "article"])
                context = row.get_text(" ", strip=True)[:1200] if row else ""
                label = anchor.get_text(" ", strip=True) + " " + context + " " + unquote(target)
                path = urlsplit(target).path.lower()
                download = "/api/article/download/" in path and re.search(r"\b(?:pdf|slides|factsheet)\b", label, re.I)
                if not (_RESULT.search(label) or path.endswith(".pdf") or download) or _ANNOUNCEMENT.search(label):
                    continue
                previous = self._candidate_hints.get(target, {})
                self._candidate_hints[target] = _candidate_hint(target, label, profile, previous.get("required", False))
                years = re.findall(r"20\d{2}", label)
                score = (max(years, default="0000"), bool(_RESULT.search(label)), label.casefold())
                scored.append((score, target))
            except (ValueError, TypeError):
                continue
        scored.sort(reverse=True)
        return list(dict.fromkeys(target for _, target in scored))[:30]

    def _document(self, url: str, raw: bytes, kind: str, profile: dict[str, Any], issuer_id: str) -> dict[str, Any]:
        if self._index(url, profile):
            raise ValueError("index_is_not_document")
        soup = BeautifulSoup(raw, "html.parser") if kind == ".html" else None
        heading = " ".join(node.get_text(" ", strip=True) for node in soup.find_all(["title", "h1", "h2", "h3"])[:8]) if soup else ""
        if soup and (not _RESULT.search(heading) or _ANNOUNCEMENT.search(heading)):
            raise ValueError("not_reported_earnings")
        company_root = (self.base_dir / profile["ticker"]).resolve()
        directory = (company_root / "ir").resolve()
        if not company_root.is_relative_to(self.base_dir) or not directory.is_relative_to(company_root):
            raise ValueError("cache_path_outside_company")
        directory.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=directory, suffix=kind, delete=False) as output:
                temporary = Path(output.name)
                output.write(raw)
            content = extract_official_text(temporary)
            compact = re.sub(r"\s+", " ", content)
            identity_text = re.sub(r"\s+", "", compact).casefold()
            if not any(re.sub(r"\s+", "", alias).casefold() in identity_text for alias in profile["aliases"]):
                raise ValueError("company_not_in_document")
            if not re.search(r"(?:revenue|sales|매출).{0,100}\d|\d.{0,60}(?:revenue|sales|매출)", compact, re.I) or not re.search(r"(?:profit|income|earnings per share|영업이익|순이익).{0,100}\d|\d.{0,60}(?:profit|income|영업이익|순이익)", compact, re.I):
                raise ValueError("reported_financial_values_missing")
            period = _period(content, profile)
            if not period:
                raise ValueError("report_period_missing")
            published = _published(soup, content, period)
            if not published or period > published or published > datetime.now(_KST).date():
                raise ValueError("publication_date_missing_or_future")
            identifier = "IR-" + _digest(url.encode() + raw)[:24]
            original_path, text_path = directory / (identifier + kind), directory / (identifier + ".txt")
            temporary.replace(original_path)
            temporary = None
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory, suffix=".txt", delete=False) as output:
                temporary = Path(output.name)
                output.write(content)
            temporary.replace(text_path)
            temporary = None
            return {"document_id": identifier, "company_name": profile["company_name"], "ticker": profile["ticker"],
                    "document_type": "earnings", "source_type": "official", "provider": "official_ir", "issuer_id": issuer_id,
                    "source_url": url, "published_at": published.isoformat(), "report_date": period.isoformat(),
                    "identity_verified": True, "original_path": str(original_path), "text_path": str(text_path),
                    "original_hash": _digest(raw), "content_hash": _digest(content.encode()), "content": content}
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)

    def collect(self, company: str, ticker: str, issuer_id: str = "", limit: int = 2, source_urls: list[str] | tuple[str, ...] | None = None) -> dict[str, Any]:
        profile = get_profile(company, ticker)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 5:
            raise ValueError("invalid_document_limit")
        if source_urls is not None and (not isinstance(source_urls, (list, tuple)) or not 1 <= len(source_urls) <= 10):
            raise ValueError("invalid_source_list")
        if source_urls is not None and not all(isinstance(value, str) for value in source_urls):
            raise ValueError("invalid_source_list")
        if not isinstance(issuer_id, str):
            raise ValueError("issuer_identity_mismatch")
        expected = str(profile.get("sec_cik") or "")
        if profile["market"] == "us":
            if issuer_id and issuer_id != expected:
                raise ValueError("issuer_identity_mismatch")
            issuer_id = expected
        elif issuer_id and not re.fullmatch(r"\d{8}", issuer_id):
            raise ValueError("issuer_identity_mismatch")
        queue = list(dict.fromkeys(source_urls if source_urls is not None else (source["url"] for source in profile["ir_sources"])))
        seeds = set(queue)
        self._candidate_hints = {}
        declared = {source["url"] for source in profile["ir_sources"] if source.get("is_document") is True}
        for source in queue:
            required = source in declared or (source_urls is not None and not self._index(source, profile))
            self._candidate_hints[source] = _candidate_hint(source, "", profile, required)
        documents, failures, visited, hashes, failed_hints = [], [], set(), set(), []
        while queue and len(visited) < MAX_FETCHES and len(documents) < limit:
            source = queue.pop(0)
            if source in visited:
                continue
            visited.add(source)
            try:
                url, raw, kind = self._fetch(source, profile)
                if kind == ".html":
                    links = self._links(url, raw, profile)
                    queue.extend(link for link in links if link not in visited and link not in queue)
                    # Undated PDF lists must not exhaust the budget before dated release pages.
                    queue.sort(key=lambda target: (target not in seeds, urlsplit(target).path.lower().endswith(".pdf")))
                if self._index(url, profile):
                    continue
                document = self._document(url, raw, kind, profile, issuer_id)
                if document["content_hash"] not in hashes:
                    documents.append(document)
                    hashes.add(document["content_hash"])
            except (ValueError, OSError, PyPdfError) as error:
                code = str(error) if type(error) is ValueError and re.fullmatch(r"[a-z_0-9]+", str(error)) else type(error).__name__
                failures.append({"stage": "official_ir", "code": code})
                failed_hints.append(self._candidate_hints.get(source, _candidate_hint(source, "", profile)))
        documents.sort(key=lambda document: document["published_at"], reverse=True)
        if not documents and not failures:
            failures.append({"stage": "official_ir", "code": "dated_earnings_document_missing"})
        pending = [hint for url, hint in self._candidate_hints.items() if url not in visited and (hint["required"] or hint["period"] or hint["published"] or hint["month"] or hint["fiscal"])]
        latest_failed = not documents or any(_newer_candidate_uncovered(hint, documents, profile) for hint in [*failed_hints, *pending])
        return {"documents": documents, "failures": failures, "latest_earnings_failed": latest_failed}
