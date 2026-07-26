import ipaddress
import socket
from typing import Any
from urllib.parse import urljoin, urlsplit

import requests


class SearxngSearch:
    TIMEOUT = (3, 20)

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "MarketCouncil/1.0 web-collector",
        })

    def search(
        self,
        query: str,
        limit: int = 10,
        categories: str = "general",
        time_range: str | None = "month",
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "q": query,
            "format": "json",
            "categories": categories,
            "language": "all",
            "safesearch": 1,
        }
        if time_range:
            params["time_range"] = time_range

        try:
            response = self.session.get(
                urljoin(f"{self.base_url}/", "search"),
                params=params,
                timeout=self.TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as error:
            raise RuntimeError(
                "SearXNG 검색에 실패했습니다. 로컬 SearXNG 실행 상태를 확인하세요."
            ) from error
        except requests.JSONDecodeError as error:
            raise RuntimeError(
                "SearXNG JSON 출력이 비활성화되어 있거나 응답 형식이 잘못되었습니다."
            ) from error

        results = payload.get("results", [])
        if not isinstance(results, list):
            return []

        normalized: list[dict[str, Any]] = []
        for result in results:
            if not isinstance(result, dict):
                continue
            url = str(result.get("url", "")).strip()
            if not self.is_public_web_url(url):
                continue
            normalized.append({
                "title": str(result.get("title", "")).strip(),
                "url": url,
                "snippet": str(result.get("content", "")).strip(),
                "published_date": str(
                    result.get("publishedDate")
                    or result.get("published_date")
                    or ""
                ).strip(),
                "engines": result.get("engines", []),
            })
            if len(normalized) >= limit:
                break
        return normalized

    @staticmethod
    def is_public_web_url(url: str) -> bool:
        try:
            parts = urlsplit(url)
        except ValueError:
            return False
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            return False
        if parts.username or parts.password:
            return False
        if parts.hostname.lower() == "localhost":
            return False

        try:
            addresses = socket.getaddrinfo(
                parts.hostname,
                parts.port or (443 if parts.scheme == "https" else 80),
                type=socket.SOCK_STREAM,
            )
        except socket.gaierror:
            return False
        return bool(addresses) and all(
            ipaddress.ip_address(address[4][0]).is_global
            for address in addresses
        )
