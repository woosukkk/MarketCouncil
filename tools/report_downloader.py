import ipaddress
import re
import socket
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import requests

from rag.document_registry import INBOX_DIR, DocumentRegistry


class ReportDownloadSkipped(Exception):
    """직접 수집할 PDF가 없는 정상적인 건너뜀 상태."""


class _PdfLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attributes = dict(attrs)
        candidate = ""

        if tag == "a":
            candidate = attributes.get("href") or ""
        elif tag in {"iframe", "embed"}:
            candidate = attributes.get("src") or ""
        elif tag == "object":
            candidate = attributes.get("data") or ""

        path = urlsplit(candidate).path.lower()
        if candidate and path.endswith(".pdf"):
            self.links.append(candidate)


class ReportDownloader:
    MAX_BYTES = 25 * 1024 * 1024
    MAX_REDIRECTS = 3
    TIMEOUT = (5, 30)

    def __init__(self) -> None:
        self.registry = DocumentRegistry()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "MarketCouncil/1.0 report-collector",
        })

    def download(
        self,
        url: str,
        discover_pdf_link: bool = True,
    ) -> Path:
        current_url = url

        for _ in range(self.MAX_REDIRECTS + 1):
            self._validate_public_https_url(current_url)

            try:
                response = self.session.get(
                    current_url,
                    stream=True,
                    timeout=self.TIMEOUT,
                    allow_redirects=False,
                )
            except requests.RequestException as error:
                if not self._looks_like_pdf_url(current_url):
                    raise ReportDownloadSkipped(
                        "웹페이지 접근이 제한되어 PDF 첨부파일을 확인하지 못했습니다."
                    ) from error
                raise RuntimeError("리포트 다운로드에 실패했습니다.") from error

            if response.is_redirect or response.is_permanent_redirect:
                location = response.headers.get("Location")
                response.close()
                if not location:
                    raise ValueError("리다이렉트 주소가 없습니다.")
                current_url = urljoin(current_url, location)
                continue

            try:
                if response.status_code >= 400 and not self._looks_like_pdf_url(
                    current_url
                ):
                    raise ReportDownloadSkipped(
                        f"웹페이지 접근 제한 또는 오류 상태: HTTP {response.status_code}"
                    )
                response.raise_for_status()
                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > self.MAX_BYTES:
                    raise ValueError("리포트 파일이 25MB를 초과합니다.")

                content = bytearray()
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    if not chunk:
                        continue
                    content.extend(chunk)
                    if len(content) > self.MAX_BYTES:
                        raise ValueError("리포트 파일이 25MB를 초과합니다.")
            except requests.RequestException as error:
                raise RuntimeError("리포트 응답을 읽지 못했습니다.") from error
            finally:
                response.close()

            if not content.startswith(b"%PDF"):
                if discover_pdf_link and self._is_html(response, content):
                    pdf_url = self._find_pdf_url(content, current_url)
                    if pdf_url:
                        return self.download(
                            pdf_url,
                            discover_pdf_link=False,
                        )
                    raise ReportDownloadSkipped(
                        "HTML 페이지에서 PDF 첨부파일을 찾지 못했습니다."
                    )
                raise ReportDownloadSkipped(
                    "직접 다운로드 가능한 PDF가 아닙니다."
                )

            filename = self._filename(response, current_url)
            destination = self.registry.unique_destination(
                INBOX_DIR,
                filename,
            )
            destination.write_bytes(content)
            return destination

        raise ValueError("리다이렉트 횟수가 너무 많습니다.")

    @staticmethod
    def _looks_like_pdf_url(url: str) -> bool:
        return urlsplit(url).path.lower().endswith(".pdf")

    @staticmethod
    def _is_html(
        response: requests.Response,
        content: bytes | bytearray,
    ) -> bool:
        content_type = response.headers.get("Content-Type", "").lower()
        prefix = bytes(content[:200]).lstrip().lower()
        return (
            "text/html" in content_type
            or prefix.startswith(b"<!doctype html")
            or prefix.startswith(b"<html")
        )

    @staticmethod
    def _find_pdf_url(
        content: bytes | bytearray,
        page_url: str,
    ) -> str:
        parser = _PdfLinkParser()
        parser.feed(bytes(content).decode("utf-8", errors="ignore"))
        if not parser.links:
            return ""
        return urljoin(page_url, parser.links[0])

    @staticmethod
    def _validate_public_https_url(url: str) -> None:
        parts = urlsplit(url)
        if parts.scheme.lower() != "https" or not parts.hostname:
            raise ValueError("HTTPS 공개 URL만 다운로드할 수 있습니다.")
        if parts.username or parts.password:
            raise ValueError("인증정보가 포함된 URL은 허용하지 않습니다.")

        try:
            addresses = socket.getaddrinfo(
                parts.hostname,
                parts.port or 443,
                type=socket.SOCK_STREAM,
            )
        except socket.gaierror as error:
            raise ValueError("리포트 호스트를 확인할 수 없습니다.") from error

        for address in addresses:
            ip = ipaddress.ip_address(address[4][0])
            if not ip.is_global:
                raise ValueError("내부 또는 비공개 네트워크 URL은 허용하지 않습니다.")

    @staticmethod
    def _filename(response: requests.Response, url: str) -> str:
        disposition = response.headers.get("Content-Disposition", "")
        match = re.search(
            r"filename\*?=(?:UTF-8''|\")?([^\";]+)",
            disposition,
            flags=re.IGNORECASE,
        )
        candidate = unquote(match.group(1)) if match else ""
        if not candidate:
            candidate = unquote(Path(urlsplit(url).path).name)

        candidate = Path(candidate).name
        candidate = re.sub(r"[^0-9A-Za-z가-힣._-]+", "_", candidate)
        if not candidate.lower().endswith(".pdf"):
            candidate = f"{candidate or 'report'}.pdf"
        return candidate
