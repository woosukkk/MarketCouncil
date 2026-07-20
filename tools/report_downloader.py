import ipaddress
import re
import socket
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import requests

from rag.document_registry import INBOX_DIR, DocumentRegistry


class ReportDownloader:
    MAX_BYTES = 25 * 1024 * 1024
    MAX_REDIRECTS = 3
    TIMEOUT = (5, 30)

    def __init__(self) -> None:
        self.registry = DocumentRegistry()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "BULL-AGNET/1.0 report-collector",
        })

    def download(self, url: str) -> Path:
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
                raise RuntimeError("리포트 다운로드에 실패했습니다.") from error

            if response.is_redirect or response.is_permanent_redirect:
                location = response.headers.get("Location")
                response.close()
                if not location:
                    raise ValueError("리다이렉트 주소가 없습니다.")
                current_url = urljoin(current_url, location)
                continue

            try:
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
                raise ValueError("직접 다운로드 가능한 PDF URL이 아닙니다.")

            filename = self._filename(response, current_url)
            destination = self.registry.unique_destination(
                INBOX_DIR,
                filename,
            )
            destination.write_bytes(content)
            return destination

        raise ValueError("리다이렉트 횟수가 너무 많습니다.")

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
