"""Bounded local official-filing cache; no model calls or vector indexing."""
import calendar
import hashlib
import json
import os
import re
import tempfile
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from bs4 import BeautifulSoup
from pypdf.errors import PyPdfError

from tools.dart_collector import DartCollector
from tools.evidence_dates import parse_evidence_date
from tools.sec_edgar_collector import SecEdgarCollector


MAX_ORIGINAL_BYTES = 50 * 1024 * 1024
MAX_ZIP_BYTES = 25 * 1024 * 1024
MAX_ZIP_MEMBERS = 1000
MAX_TEXT_CHARACTERS = 4_000_000
MIN_TEXT_CHARACTERS = 1000
_KST = timezone(timedelta(hours=9))


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _markup_text(value: bytes) -> str:
    soup = BeautifulSoup(value, "html.parser")
    for element in soup.find_all(["script", "style", "nav", "noscript", "header", "footer", "svg"]):
        element.decompose()
    return "\n".join(soup.stripped_strings)


def extract_official_text(path: Path) -> str:
    """Reject oversized archives before reading any expanded member."""
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_ORIGINAL_BYTES:
        raise ValueError("invalid_original_size")
    suffix = path.suffix.lower()
    if suffix == ".zip":
        try:
            with zipfile.ZipFile(path) as archive:
                members = archive.infolist()
                if len(members) > MAX_ZIP_MEMBERS or sum(member.file_size for member in members) > MAX_ZIP_BYTES:
                    raise ValueError("archive_limit_exceeded")
                parts = []
                for member in members:
                    if member.flag_bits & 1:
                        raise ValueError("encrypted_archive")
                    if Path(member.filename).suffix.lower() in {".xml", ".html", ".htm", ".xhtml", ".txt"}:
                        parts.append(_markup_text(archive.read(member)))
                text = "\n\n".join(parts)
        except (zipfile.BadZipFile, RuntimeError) as error:
            raise ValueError("invalid_archive") from error
    elif suffix == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(path)
        if len(reader.pages) > 500:
            raise ValueError("pdf_page_limit_exceeded")
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    elif suffix in {".html", ".htm", ".xhtml", ".xml", ".txt"}:
        text = _markup_text(path.read_bytes())
    else:
        raise ValueError("unsupported_original_type")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    _validate_text(text)
    return text


def _validate_text(text: str) -> None:
    if not MIN_TEXT_CHARACTERS <= len(text.strip()) <= MAX_TEXT_CHARACTERS:
        raise ValueError("invalid_text_length")
    beginning = text[:2000].casefold()
    if any(marker in beginning for marker in (
        "access denied", "request rate threshold exceeded", "undeclared automated tool",
        "just a moment", "verify you are human", "captcha", "접근이 제한", "요청하신 페이지를 찾을 수 없",
    )):
        raise ValueError("blocked_response_body")


def _document_type(form: str) -> str:
    if form.upper() in {"10-K", "20-F", "40-F"} or "사업보고서" in form:
        return "annual"
    if form.upper() == "10-Q" or any(name in form for name in ("분기보고서", "반기보고서")):
        return "interim"
    raise ValueError("unsupported_filing_form")


def _report_date(metadata: dict[str, Any]) -> str:
    value = parse_evidence_date(metadata.get("report_date"))
    if value:
        return value.isoformat()
    # DART explicitly labels the fiscal ending month in the report title.
    match = re.search(r"\((\d{4})\.(\d{2})\)", str(metadata.get("form_type", "")))
    if match:
        year, month = map(int, match.groups())
        try:
            return f"{year:04d}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}"
        except (ValueError, calendar.IllegalMonthError):
            pass
    return ""


class CompanyEvidenceCollector:
    def __init__(self, base_dir: Path = Path("documents/company_evidence")) -> None:
        self.base_dir = base_dir.resolve()

    @staticmethod
    def _profile(company_name: str, ticker: str) -> dict[str, Any]:
        from tools.company_profiles import get_profile
        return get_profile(company_name, ticker)

    def _root(self, ticker: str) -> Path:
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9.^=-]{0,29}", ticker):
            raise ValueError("invalid_ticker")
        root = (self.base_dir / ticker).resolve()
        if not root.is_relative_to(self.base_dir):
            raise ValueError("company_cache_outside_base")
        return root

    @staticmethod
    def _file(root: Path, value: object) -> Path:
        if not isinstance(value, str) or not value:
            raise ValueError("missing_cache_path")
        path = Path(value)
        path = (path if path.is_absolute() else root / path).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError("cache_path_outside_company_or_missing")
        return path

    @staticmethod
    def _identity(document: dict[str, Any], profile: dict[str, Any], issuer_id: str) -> None:
        if document.get("company_name") != profile["company_name"] or document.get("ticker") != profile["ticker"]:
            raise ValueError("company_identity_mismatch")
        if document.get("identity_verified") is not True:
            raise ValueError("unverified_issuer")
        provider, identifier = document.get("provider"), str(document.get("issuer_id", ""))
        source = urlsplit(str(document.get("source_url", "")))
        if source.scheme != "https" or source.username or source.password or source.port not in (None, 443):
            raise ValueError("invalid_official_url")
        if provider == "open_dart":
            if profile["market"] != "kr" or not re.fullmatch(r"\d{8}", identifier) or identifier != issuer_id:
                raise ValueError("issuer_identity_mismatch")
            receipt = str(document.get("document_id", ""))
            if source.hostname != "dart.fss.or.kr" or source.path != "/dsaf001/main.do" or not re.fullmatch(r"\d{14}", receipt) or parse_qs(source.query).get("rcpNo") != [receipt]:
                raise ValueError("unverified_filing_url")
        elif provider == "sec_edgar":
            expected = str(profile.get("sec_cik") or "").zfill(10)
            if profile["market"] != "us" or not re.fullmatch(r"\d{10}", identifier) or identifier != expected:
                raise ValueError("issuer_identity_mismatch")
            accession = str(document.get("document_id", ""))
            prefix = f"/Archives/edgar/data/{int(identifier)}/{accession.replace('-', '')}/"
            if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession) or source.hostname not in {"www.sec.gov", "sec.gov"} or not source.path.startswith(prefix) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,200}", source.path[len(prefix):]):
                raise ValueError("unverified_filing_url")
        elif provider == "official_ir":
            sources = profile.get("ir_sources", ())
            if not any(source.hostname == item["host"] and any(source.path.casefold().startswith(prefix.casefold()) for prefix in item["path_prefixes"]) for item in sources):
                raise ValueError("unverified_ir_url")
        else:
            raise ValueError("unsupported_provider")

    def _hydrate(self, document: dict[str, Any], root: Path, profile: dict[str, Any], issuer_id: str) -> dict[str, Any]:
        self._identity(document, profile, issuer_id)
        published, period = parse_evidence_date(document.get("published_at")), parse_evidence_date(document.get("report_date"))
        if not published or published > datetime.now(_KST).date() or not period or period > published:
            raise ValueError("invalid_document_dates")
        if document.get("document_type") not in {"annual", "interim", "earnings", "report"}:
            raise ValueError("invalid_document_type")
        original, text_path = self._file(root, document.get("original_path")), self._file(root, document.get("text_path"))
        if original.stat().st_size > MAX_ORIGINAL_BYTES or text_path.stat().st_size > MAX_TEXT_CHARACTERS * 4:
            raise ValueError("invalid_cache_size")
        if _sha(original.read_bytes()) != document.get("original_hash"):
            raise ValueError("original_hash_mismatch")
        content = text_path.read_text(encoding="utf-8")
        _validate_text(content)
        if _sha(content.encode("utf-8")) != document.get("content_hash"):
            raise ValueError("text_hash_mismatch")
        return {**document, "original_path": str(original), "text_path": str(text_path), "content": content}

    @staticmethod
    def _selection(result: dict[str, Any], provider: str, limit: int = 10) -> tuple[list[str], list[str]]:
        if not isinstance(result, dict):
            raise ValueError("invalid_current_filing_selection")
        pattern = r"\d{14}" if provider == "open_dart" else r"\d{10}-\d{2}-\d{6}"
        requested, required = result.get("requested_ids"), result.get("latest_required_ids")
        for identifiers in (requested, required):
            if (not isinstance(identifiers, list) or len(identifiers) > limit
                    or any(not isinstance(value, str) or not re.fullmatch(pattern, value) for value in identifiers)
                    or len(set(identifiers)) != len(identifiers)):
                raise ValueError("invalid_current_filing_selection")
        if not set(required).issubset(requested):
            raise ValueError("invalid_current_filing_selection")
        return requested, required

    @classmethod
    def _latest_failed(cls, manifest: dict[str, Any], documents: list[dict[str, Any]], profile: dict[str, Any]) -> bool:
        """A body must pass the same acceptance rules as the gate, not merely exist on disk."""
        from tools.evidence_readiness import evaluate_readiness
        try:
            requested, required = cls._selection(manifest, profile["provider"])
        except ValueError:
            return True
        if not requested or not required:
            return True
        accepted = set()
        for document in documents:
            if document.get("provider") != profile["provider"]:
                continue
            single = evaluate_readiness({"company_name": profile["company_name"], "ticker": profile["ticker"], "documents": [document]})
            accepted.update(row["document_id"] for row in single["documents"])
        return not set(required).issubset(accepted)

    def collect(self, company_name: str, ticker: str, limit: int = 5) -> dict[str, Any]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 2 <= limit <= 10:
            raise ValueError("limit_must_be_between_2_and_10")
        profile = self._profile(company_name, ticker)
        root = self._root(profile["ticker"])
        root.mkdir(parents=True, exist_ok=True)
        if not (root / "raw").resolve().is_relative_to(root):
            raise ValueError("raw_cache_outside_company")
        provider = profile["provider"]
        failures: list[dict[str, str]] = []
        issuer_id = str(profile.get("sec_cik") or "")
        try:
            collector = (DartCollector(os.getenv("DART_API_KEY", ""), root / "raw") if provider == "open_dart"
                         else SecEdgarCollector(os.getenv("SEC_USER_AGENT", ""), root / "raw"))
            result = collector.collect(profile["company_name"], profile["ticker"], limit=limit, periodic_only=True)
            requested, required = self._selection(result, provider, limit)
            issuer_id = str(result.get("issuer_id", issuer_id))
            failures.extend({"stage": "download", "code": "download_failed", "document_id": str(row.get("id", ""))} for row in result.get("failed", []))
        except (OSError, ValueError, RuntimeError, KeyError, TypeError, AttributeError):
            # A standalone collector failure must also invalidate a previously ready disk cache.
            cached = self.load(company_name, ticker)
            cached.update(provider=provider, issuer_id=str(cached.get("issuer_id") or issuer_id),
                          collected_at=datetime.now(_KST).isoformat(timespec="seconds"),
                          requested_ids=[], latest_required_ids=[], latest_primary_failed=True)
            cached["failures"].append({"stage": "collection", "code": "source_unavailable"})
            self.save(cached)
            return cached
        documents = []
        directory = root / "raw" / ("dart" if provider == "open_dart" else "sec") / collector._safe_name(profile["company_name"])
        # Never discover old raw files: only the current authoritative filing list may supply evidence.
        for identifier in requested:
            metadata_path = directory / (identifier + ".metadata.json")
            try:
                if not metadata_path.resolve().is_relative_to(root):
                    raise ValueError("metadata_outside_company")
                if metadata_path.stat().st_size > 100_000:
                    raise ValueError("metadata_too_large")
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                if not isinstance(metadata, dict) or metadata.get("filing_id") != identifier:
                    raise ValueError("invalid_metadata")
                expected_ticker = profile["ticker"].split(".", 1)[0] if provider == "open_dart" else profile["ticker"]
                if metadata.get("provider") != provider or metadata.get("ticker") != expected_ticker or metadata.get("identity_verified") is not True:
                    raise ValueError("unverified_cached_metadata")
                original = self._file(root, metadata.get("original_path"))
                if not 0 < original.stat().st_size <= MAX_ORIGINAL_BYTES:
                    raise ValueError("invalid_original_size")
                published = parse_evidence_date(metadata.get("filed_at"))
                document = {
                    "document_id": identifier, "company_name": profile["company_name"], "ticker": profile["ticker"],
                    "document_type": _document_type(str(metadata.get("form_type", ""))), "source_type": "official",
                    "provider": provider, "issuer_id": str(metadata.get("corp_code") or metadata.get("cik") or ""),
                    "source_url": metadata.get("source_url", ""), "published_at": published.isoformat() if published else "",
                    "report_date": _report_date(metadata), "identity_verified": True,
                    "original_path": str(original.relative_to(root)), "original_hash": _sha(original.read_bytes()),
                }
                self._identity(document, profile, issuer_id)
                content = extract_official_text(original)
                text_path = root / "text" / f"{identifier}.txt"
                if not text_path.resolve().is_relative_to(root):
                    raise ValueError("text_cache_outside_company")
                text_path.parent.mkdir(exist_ok=True)
                text_path.write_text(content, encoding="utf-8")
                document.update(text_path=str(text_path.relative_to(root)), content_hash=_sha(content.encode("utf-8")))
                documents.append(self._hydrate(document, root, profile, issuer_id))
            except (OSError, ValueError, KeyError, TypeError, PyPdfError) as error:
                code = str(error) if type(error) is ValueError and re.fullmatch(r"[a-z_0-9]+", str(error)) else type(error).__name__
                failures.append({"stage": "validation", "code": code, "document_id": identifier})
        documents.sort(key=lambda document: document["published_at"], reverse=True)
        chosen = [next((doc for doc in documents if doc["document_type"] == kind), None) for kind in ("annual", "interim")]
        selected = [doc for doc in chosen if doc is not None]
        documents = (selected + [doc for doc in documents if doc not in selected])[:limit]
        manifest = {"company_name": profile["company_name"], "ticker": profile["ticker"], "provider": provider,
                    "issuer_id": issuer_id, "collected_at": datetime.now(_KST).isoformat(timespec="seconds"),
                    "requested_ids": requested, "latest_required_ids": required,
                    "documents": documents, "failures": failures}
        manifest["latest_primary_failed"] = self._latest_failed(manifest, documents, profile)
        self.save(manifest)
        return manifest

    def save(self, manifest: dict[str, Any]) -> None:
        """Persist only validated file-backed documents, preserving the prior cache on failure."""
        profile = self._profile(manifest["company_name"], manifest["ticker"])
        root = self._root(profile["ticker"])
        root.mkdir(parents=True, exist_ok=True)
        documents = manifest.get("documents", [])
        if not isinstance(documents, list) or len(documents) > 100:
            raise ValueError("invalid_document_list")
        documents = [self._hydrate(document, root, profile, str(manifest.get("issuer_id", ""))) for document in documents]
        cache = {key: manifest[key] for key in ("company_name", "ticker", "provider", "issuer_id", "collected_at", "failures", "requested_ids", "latest_required_ids", "latest_primary_failed", "latest_earnings_failed") if key in manifest}
        cache["documents"] = [{key: value for key, value in doc.items() if key != "content"} for doc in documents]
        for document in cache["documents"]:
            for key in ("original_path", "text_path"):
                document[key] = str(Path(document[key]).relative_to(root))
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=root, suffix=".tmp", delete=False) as output:
            temporary = Path(output.name)
            json.dump(cache, output, ensure_ascii=False, indent=2)
        try:
            temporary.replace(root / "manifest.json")
        finally:
            temporary.unlink(missing_ok=True)

    def load(self, company_name: str, ticker: str) -> dict[str, Any]:
        profile = self._profile(company_name, ticker)
        root = self._root(profile["ticker"])
        empty = {"company_name": profile["company_name"], "ticker": profile["ticker"], "collected_at": "", "documents": [], "failures": []}
        path = root / "manifest.json"
        if not path.is_file():
            return {**empty, "failures": [{"stage": "cache", "code": "manifest_missing"}]}
        try:
            path = self._file(root, "manifest.json")
            if path.stat().st_size > 1_000_000:
                raise ValueError("manifest_too_large")
            manifest = json.loads(path.read_text(encoding="utf-8"))
            if manifest.get("company_name") != profile["company_name"] or manifest.get("ticker") != profile["ticker"]:
                raise ValueError("company_identity_mismatch")
            documents = manifest.get("documents")
            if not isinstance(documents, list) or len(documents) > 100:
                raise ValueError("invalid_document_list")
            hydrated, failures = [], []
            for document in documents:
                try:
                    hydrated.append(self._hydrate(document, root, profile, str(manifest.get("issuer_id", ""))))
                except (OSError, ValueError, KeyError, TypeError) as error:
                    code = str(error) if type(error) is ValueError and re.fullmatch(r"[a-z_0-9]+", str(error)) else type(error).__name__
                    failures.append({"stage": "cache_validation", "code": code})
            loaded = {**manifest, "documents": hydrated, "failures": [*manifest.get("failures", []), *failures]}
            if manifest.get("provider") in {"open_dart", "sec_edgar"} or any(doc.get("provider") in {"open_dart", "sec_edgar"} for doc in hydrated):
                loaded["latest_primary_failed"] = bool(manifest.get("latest_primary_failed")) or self._latest_failed(manifest, hydrated, profile)
            return loaded
        except (OSError, ValueError, AttributeError, TypeError):
            return {**empty, "failures": [{"stage": "cache", "code": "invalid_manifest"}]}
