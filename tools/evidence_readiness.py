"""Minimum local primary-evidence coverage, not an AI or investment quality score."""
import hashlib
import json
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit, urlunsplit

from tools.company_profiles import get_profile
from tools.evidence_dates import parse_evidence_date
from tools.evidence_text import is_navigation_text


POLICY_VERSION = "primary-v1"
DOCUMENT_TYPES = ("annual", "interim", "earnings", "report")
MISSING_CODES = ("annual_missing", "recent_financial_missing", "earnings_missing")
MIN_BODY_CHARS = {"annual": 1000, "interim": 1000, "earnings": 800, "report": 600}
_HASH = re.compile(r"[a-f0-9]{64}")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}")
_ERROR = re.compile(r"access denied|undeclared automated tool|request rate threshold exceeded|enable javascript|captcha verification|404 not found|service unavailable|unusual traffic", re.I)


def _cutoff(value: object = None) -> date:
    if value is None:
        return datetime.now(timezone(timedelta(hours=9))).date()
    result = parse_evidence_date(value)
    if result is None:
        raise ValueError("근거 기준일은 ISO 날짜여야 합니다.")
    return result


def _official_url(profile: dict[str, Any], value: object, provider: str | None = None,
                  issuer_id: object = None) -> str:
    if not isinstance(value, str) or len(value) > 2000 or re.search(r"[\x00-\x20\x7f]", value):
        raise ValueError("invalid_source")
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443):
            raise ValueError("invalid_source")
        path = unquote(parsed.path)
        if any(part in (".", "..") for part in path.split("/")) or "\\" in path:
            raise ValueError("invalid_source")
        if host == "dart.fss.or.kr":
            receipt = parse_qs(parsed.query).get("rcpNo", [])
            if profile["market"] != "kr" or parsed.path != "/dsaf001/main.do" or len(receipt) != 1 or not re.fullmatch(r"\d{14}", receipt[0]):
                raise ValueError("invalid_source")
            if provider is not None and (provider != "open_dart" or not re.fullmatch(r"\d{8}", str(issuer_id))):
                raise ValueError("invalid_issuer")
            return urlunsplit(("https", host, parsed.path, "rcpNo=" + receipt[0], ""))
        if host == "www.sec.gov":
            match = re.fullmatch(r"/Archives/edgar/data/(\d+)/(\d{18})/[^/]+", path)
            if profile["market"] != "us" or not match or int(match[1]) != int(profile["sec_cik"]):
                raise ValueError("invalid_source")
            if provider is not None and (provider != "sec_edgar" or not str(issuer_id).isdigit() or int(str(issuer_id)) != int(profile["sec_cik"])):
                raise ValueError("invalid_issuer")
        else:
            if provider is not None and provider != "official_ir":
                raise ValueError("invalid_source")
            allowed = [source for source in (*profile["ir_sources"], *profile.get("filing_sources", ())) if source["host"] == host]
            if not any(path.casefold().startswith(prefix.casefold()) for source in allowed for prefix in source["path_prefixes"]):
                raise ValueError("invalid_source")
            if any(source.get("is_document") is not True and path.rstrip("/").casefold() == urlsplit(source["url"]).path.rstrip("/").casefold() for source in allowed):
                raise ValueError("index_is_not_document")
        return urlunsplit(("https", host, parsed.path, "", ""))
    except (TypeError, OverflowError) as error:
        raise ValueError("invalid_source") from error


def _requirements(documents: list[dict[str, Any]], cutoff: date) -> list[str]:
    annual = [item for item in documents if item["document_type"] == "annual"
              and 0 <= (cutoff - date.fromisoformat(item["report_date"])).days <= 550
              and 0 <= (cutoff - date.fromisoformat(item["published_at"])).days <= 550]
    interim = [item for item in documents if item["document_type"] == "interim"
               and 0 <= (cutoff - date.fromisoformat(item["report_date"])).days <= 200
               and 0 <= (cutoff - date.fromisoformat(item["published_at"])).days <= 200]
    # A newly filed annual statement is the latest financial period after year-end.
    recent_annual = [item for item in annual if (cutoff - date.fromisoformat(item["report_date"])).days <= 200
                     and (cutoff - date.fromisoformat(item["published_at"])).days <= 120]
    earnings = [item for item in documents if item["document_type"] == "earnings"
                and 0 <= (cutoff - date.fromisoformat(item["report_date"])).days <= 200
                and 0 <= (cutoff - date.fromisoformat(item["published_at"])).days <= 200]
    return [code for code, good in zip(MISSING_CODES, (bool(annual), bool(interim or recent_annual), bool(earnings))) if not good]


def _corpus_hash(company: str, ticker: str, documents: list[dict[str, Any]]) -> str:
    content = {"policy_version": POLICY_VERSION, "company_name": company, "ticker": ticker,
               "documents": sorted(documents, key=lambda item: (item["document_id"], item["content_hash"]))}
    return hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def evaluate_readiness(manifest: dict[str, Any], as_of_date: object = None) -> dict[str, Any]:
    """Evaluate actual supplied local text; never count a metadata/ready flag as proof."""
    cutoff = _cutoff(as_of_date)
    if not isinstance(manifest, dict):
        raise ValueError("근거 묶음이 객체가 아닙니다.")
    company, ticker = manifest.get("company_name"), manifest.get("ticker")
    profile = get_profile(company, ticker)
    raw = manifest.get("documents")
    if not isinstance(raw, list) or len(raw) > 200:
        raise ValueError("근거 문서 목록을 확인하세요.")
    accepted, seen, identifiers, urls = [], set(), set(), set()
    for item in sorted((item for item in raw if isinstance(item, dict)), key=lambda item: DOCUMENT_TYPES.index(item["document_type"]) if item.get("document_type") in DOCUMENT_TYPES else 4):
        try:
            get_profile(item.get("company_name"), item.get("ticker"))
            if str(item["ticker"]).upper() != profile["ticker"] or item.get("identity_verified") is not True:
                continue
            kind, text, digest = item.get("document_type"), item.get("content"), item.get("content_hash")
            if kind not in DOCUMENT_TYPES or not isinstance(text, str) or len(text) > 5_000_000:
                continue
            if len(re.sub(r"\s", "", text)) < MIN_BODY_CHARS[kind] or is_navigation_text(text) or _ERROR.search(text[:1500]):
                continue
            if item.get("body_extraction_status") in ("snippet_only", "metadata_only", "error", "unavailable") or item.get("extraction_method") in ("search_snippet", "search_snippet_fallback", "metadata", "metadata_only") or re.search(r"<(?:html|script|style)\b", text[:1500], re.I):
                continue
            if not isinstance(digest, str) or not _HASH.fullmatch(digest) or hashlib.sha256(text.encode()).hexdigest() != digest or digest in seen:
                continue
            published, period = parse_evidence_date(item.get("published_at")), parse_evidence_date(item.get("report_date"))
            if not published or not period or period > published or published > cutoff or (cutoff - published).days > 550:
                continue
            if item.get("provider") not in ("open_dart", "sec_edgar", "official_ir"):
                continue
            url = _official_url(profile, item.get("source_url"), item.get("provider"), item.get("issuer_id"))
            if url in urls or (item["provider"] == "open_dart" and parse_evidence_date(parse_qs(urlsplit(url).query)["rcpNo"][0][:8]) != published):
                continue
            identifier = item.get("document_id") or "DOC-" + hashlib.sha256((url + digest).encode()).hexdigest()[:24]
            if not isinstance(identifier, str) or not _ID.fullmatch(identifier) or identifier in identifiers:
                continue
            accepted.append({"document_id": identifier, "document_type": kind, "published_at": published.isoformat(),
                             "report_date": period.isoformat(), "content_hash": digest, "source_url": url})
            basis = item.get('date_basis')
            if basis is not None:
                if basis != 'first_retrieved' or item.get('filing_origin') != 'issuer_filing':
                    accepted.pop()
                    continue
                accepted[-1]['date_basis'] = basis
            seen.add(digest)
            identifiers.add(identifier)
            urls.add(url)
        except (ValueError, TypeError, KeyError):
            continue
    counts = {kind: sum(item["document_type"] == kind for item in accepted) for kind in DOCUMENT_TYPES}
    missing = _requirements(accepted, cutoff)
    return {"schema_version": 1, "policy_version": POLICY_VERSION, "company_name": profile["company_name"],
            "ticker": profile["ticker"], "as_of_date": cutoff.isoformat(), "status": "insufficient" if missing else "ready",
            "missing": missing, "counts": counts, "corpus_hash": _corpus_hash(profile["company_name"], profile["ticker"], accepted),
            "documents": accepted}


def validate_readiness_report(report: object, company: str, ticker: str) -> dict[str, Any]:
    """Validate report consistency, not original-text authenticity or current-day eligibility."""
    profile = get_profile(company, ticker)
    if not isinstance(report, dict) or type(report.get("schema_version")) is not int or report["schema_version"] != 1 or report.get("policy_version") != POLICY_VERSION:
        raise ValueError("근거 준비 보고서 형식을 확인하세요.")
    fields = {"schema_version", "policy_version", "company_name", "ticker", "as_of_date", "status", "missing", "counts", "corpus_hash", "documents"}
    if not fields.issubset(report) or set(report) - fields - {"selection_reason"} or ("selection_reason" in report and report["selection_reason"] not in ("new_official_event", "attention", "rotation")):
        raise ValueError("근거 준비 보고서 필드를 확인하세요.")
    identity = get_profile(report.get("company_name"), report.get("ticker"))
    if identity["ticker"] != profile["ticker"]:
        raise ValueError("근거 준비 보고서의 기업이 다릅니다.")
    cutoff = _cutoff(report.get("as_of_date"))
    if report.get("as_of_date") != cutoff.isoformat():
        raise ValueError("근거 준비 기준일을 확인하세요.")
    documents = report.get("documents")
    if not isinstance(documents, list) or len(documents) > 200:
        raise ValueError("근거 문서 목록을 확인하세요.")
    hashes, identifiers, urls = set(), set(), set()
    for item in documents:
        core = {"document_id", "document_type", "published_at", "report_date", "content_hash", "source_url"}
        if not isinstance(item, dict) or not core.issubset(item) or set(item) - core - {'date_basis'} or ('date_basis' in item and item['date_basis'] != 'first_retrieved'):
            raise ValueError("근거 문서 형식을 확인하세요.")
        kind, digest, identifier = item.get("document_type"), item.get("content_hash"), item.get("document_id")
        if kind not in DOCUMENT_TYPES or not isinstance(digest, str) or not _HASH.fullmatch(digest) or digest in hashes or not isinstance(identifier, str) or not _ID.fullmatch(identifier) or identifier in identifiers:
            raise ValueError("근거 문서 식별자를 확인하세요.")
        published, period = parse_evidence_date(item.get("published_at")), parse_evidence_date(item.get("report_date"))
        if not published or not period or period > published or published > cutoff or (cutoff - published).days > 550 or item["published_at"] != published.isoformat() or item["report_date"] != period.isoformat():
            raise ValueError("근거 문서 시점을 확인하세요.")
        if _official_url(profile, item.get("source_url")) != item["source_url"]:
            raise ValueError("근거 문서 출처를 확인하세요.")
        if item["source_url"] in urls or (urlsplit(item["source_url"]).hostname == "dart.fss.or.kr" and parse_evidence_date(parse_qs(urlsplit(item["source_url"]).query)["rcpNo"][0][:8]) != published):
            raise ValueError("근거 문서 출처·발표일이 일치하지 않습니다.")
        hashes.add(digest)
        identifiers.add(identifier)
        urls.add(item["source_url"])
    expected_counts = {kind: sum(item["document_type"] == kind for item in documents) for kind in DOCUMENT_TYPES}
    counts, missing = report.get("counts"), _requirements(documents, cutoff)
    if not isinstance(counts, dict) or set(counts) != set(DOCUMENT_TYPES) or any(type(counts[key]) is not int or counts[key] != value for key, value in expected_counts.items()):
        raise ValueError("근거 문서 수가 일치하지 않습니다.")
    if report.get("missing") != missing or report.get("status") != ("insufficient" if missing else "ready") or report.get("corpus_hash") != _corpus_hash(profile["company_name"], profile["ticker"], documents):
        raise ValueError("근거 준비 판정이 일치하지 않습니다.")
    return report


def select_official_candidate(reports: list[dict[str, Any]], history: list[dict[str, Any]], as_of_date: object,
                              attention: dict[str, Any] | None = None, min_gap_days: int = 2) -> dict[str, Any] | None:
    """Prefer new dated primary events, then the highest attention score, otherwise rotate the oldest ready issuer."""
    cutoff = _cutoff(as_of_date)
    if not isinstance(reports, list) or not isinstance(history, list):
        raise ValueError("기업 준비 보고서와 공식 선정 기록을 확인하세요.")
    ready = []
    for report in reports:
        try:
            validate_readiness_report(report, report.get("company_name"), report.get("ticker"))
            if report["status"] != "ready" or report["as_of_date"] != cutoff.isoformat():
                continue
        except (ValueError, TypeError, AttributeError):
            continue
        prior = [item for item in history if isinstance(item, dict) and item.get("ticker") == report["ticker"]]
        dates = [parsed for item in prior if (parsed := parse_evidence_date(item.get("publication_date") or item.get("analysis_date"))) and parsed <= cutoff]
        last = max(dates, default=date.min)
        used_hashes = {doc["content_hash"] for item in prior
                       for doc in (item.get("documents") if isinstance(item.get("documents"), list) else [])
                       if isinstance(doc, dict) and isinstance(doc.get("content_hash"), str)}
        events = [doc for doc in report["documents"] if doc["document_type"] in ("annual", "interim", "earnings")
                  and doc["content_hash"] not in used_hashes and last < date.fromisoformat(doc["published_at"])
                  and 0 <= (cutoff - date.fromisoformat(doc["published_at"])).days <= 7]
        latest = max((date.fromisoformat(doc["published_at"]) for doc in events), default=date.min)
        ready.append((report, last, latest))
    if not ready:
        return None
    events = [item for item in ready if item[2] != date.min]
    if events:
        selected = sorted(events, key=lambda item: (-item[2].toordinal(), item[1], item[0]["ticker"]))[0]
        return {**selected[0], "selection_reason": "new_official_event"}
    scored = []
    for item in ready:
        signal = attention.get(item[0]["ticker"]) if isinstance(attention, dict) else None
        score = signal.get("score") if isinstance(signal, dict) else None
        if isinstance(score, (int, float)) and not isinstance(score, bool) and score >= 0:
            scored.append((item, float(score)))
    if scored:
        # Avoid repeating a just-published issuer unless every scored issuer is that recent.
        rested = [entry for entry in scored if (cutoff - entry[0][1]).days >= min_gap_days] or scored
        selected = sorted(rested, key=lambda entry: (-entry[1], entry[0][1], entry[0][0]["ticker"]))[0][0]
        return {**selected[0], "selection_reason": "attention"}
    selected = min(ready, key=lambda item: (item[1], item[0]["ticker"]))
    return {**selected[0], "selection_reason": "rotation"}
