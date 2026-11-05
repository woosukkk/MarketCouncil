import io
import json
import re
import zipfile
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import requests


class DartCollector:
    BASE_URL = "https://opendart.fss.or.kr/api"
    TIMEOUT = (5, 30)
    MAX_ORIGINAL_BYTES = 50 * 1024 * 1024

    def __init__(self, api_key: str, base_dir: Path) -> None:
        if not api_key:
            raise ValueError("DART_API_KEY가 필요합니다.")
        self.api_key = api_key
        self.base_dir = base_dir
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "MarketCouncil/1.0 regulatory-collector",
        })

    def collect(
        self,
        company_name: str,
        ticker: str,
        limit: int = 10,
        periodic_only: bool = False,
    ) -> dict[str, Any]:
        stock_code = ticker.strip().split(".", 1)[0].zfill(6)
        if periodic_only:
            corp_code = self._resolve_corp_code(company_name, stock_code, strict_stock=True)
            filings = self._list_filings(corp_code, max(limit, 12), days=550, periodic_only=True)
            annual = [row for row in filings if "사업보고서" in str(row.get("report_nm", ""))]
            interim = [row for row in filings if any(label in str(row.get("report_nm", "")) for label in ("분기보고서", "반기보고서"))]
            chosen = [*annual[:1], *interim[:1]]
            filings = (chosen + [row for row in filings if row not in chosen])[:limit]
        else:
            corp_code = self._resolve_corp_code(company_name, stock_code)
            filings = self._list_filings(corp_code, limit, days=365)
        requested_ids = list(dict.fromkeys(str(row.get("rcept_no", "")) for row in filings))
        required = chosen if periodic_only else []
        if periodic_only and annual and interim:
            annual_period = re.search(r"\((\d{4})\.(\d{2})\)", str(annual[0].get("report_nm", "")))
            interim_period = re.search(r"\((\d{4})\.(\d{2})\)", str(interim[0].get("report_nm", "")))
            if annual_period and interim_period and tuple(map(int, interim_period.groups())) <= tuple(map(int, annual_period.groups())):
                required = annual[:1]  # The newer annual period supersedes the previous year's interim.
        latest_required_ids = list(dict.fromkeys(str(row.get("rcept_no", "")) for row in required))
        target_dir = self.base_dir / "dart" / self._safe_name(company_name)
        target_dir.mkdir(parents=True, exist_ok=True)

        downloaded: list[dict[str, Any]] = []
        skipped: list[dict[str, str]] = []
        failed: list[dict[str, str]] = []

        for filing in filings:
            receipt_no = str(filing.get("rcept_no", ""))
            if not receipt_no:
                continue
            original_path = target_dir / f"{receipt_no}.zip"
            metadata_path = target_dir / f"{receipt_no}.metadata.json"
            if original_path.exists() and metadata_path.exists():
                skipped.append({
                    "id": receipt_no,
                    "reason": "already_downloaded",
                })
                continue

            try:
                content = self._download_original(receipt_no)
                original_path.write_bytes(content)
                metadata = {
                    "provider": "open_dart",
                    "identity_verified": periodic_only,
                    "company": company_name,
                    "ticker": stock_code,
                    "corp_code": corp_code,
                    "filing_id": receipt_no,
                    "form_type": filing.get("report_nm", ""),
                    "title": filing.get("report_nm", ""),
                    "filed_at": filing.get("rcept_dt", ""),
                    "publisher": filing.get("flr_nm", ""),
                    "source_url": (
                        "https://dart.fss.or.kr/dsaf001/main.do?rcpNo="
                        f"{receipt_no}"
                    ),
                    "original_path": str(original_path),
                }
                metadata_path.write_text(
                    json.dumps(metadata, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                downloaded.append(metadata)
            except Exception as error:
                original_path.unlink(missing_ok=True)
                metadata_path.unlink(missing_ok=True)
                failed.append({"id": receipt_no, "reason": str(error)})

        return {
            "provider": "open_dart",
            "issuer_id": corp_code,
            "requested_ids": requested_ids,
            "latest_required_ids": latest_required_ids,
            "downloaded": downloaded,
            "skipped": skipped,
            "failed": failed,
        }

    def _resolve_corp_code(self, company_name: str, stock_code: str, strict_stock: bool = False) -> str:
        response = self._get(
            f"{self.BASE_URL}/corpCode.xml",
            params={"crtfc_key": self.api_key},
        )
        try:
            with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                xml_text = archive.read("CORPCODE.xml").decode("utf-8")
        except (KeyError, UnicodeDecodeError, zipfile.BadZipFile) as error:
            raise RuntimeError("Open DART 기업 코드 파일을 읽지 못했습니다.") from error

        entries = re.findall(
            r"<list>.*?<corp_code>(.*?)</corp_code>.*?"
            r"<corp_name>(.*?)</corp_name>.*?"
            r"<stock_code>(.*?)</stock_code>.*?</list>",
            xml_text,
            flags=re.DOTALL,
        )
        normalized_name = re.sub(r"\s+", "", company_name).lower()
        for corp_code, corp_name, listed_code in entries:
            if listed_code.strip() == stock_code:
                return corp_code.strip()
        if strict_stock:
            raise ValueError("Open DART에서 종목코드와 일치하는 기업을 찾지 못했습니다.")
        for corp_code, corp_name, _ in entries:
            if re.sub(r"\s+", "", corp_name).lower() == normalized_name:
                return corp_code.strip()
        raise ValueError("Open DART에서 기업 고유번호를 찾지 못했습니다.")

    def list_history(
        self,
        company_name: str,
        ticker: str,
        days: int = 365 * 3,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        stock_code = ticker.strip().split(".", 1)[0].zfill(6)
        corp_code = self._resolve_corp_code(company_name, stock_code)
        segment_days = 365
        segment_limit = max(1, limit // 3)
        filings: list[dict[str, Any]] = []
        seen: set[str] = set()
        for offset in range(0, days, segment_days):
            segment_end = date.today() - timedelta(days=offset)
            for filing in self._list_filings(
                corp_code,
                segment_limit,
                days=min(segment_days, days - offset),
                end_date=segment_end,
            ):
                receipt_no = str(filing.get("rcept_no", ""))
                if receipt_no and receipt_no not in seen:
                    filings.append(filing)
                    seen.add(receipt_no)
        return filings[:limit]

    def _list_filings(
        self,
        corp_code: str,
        limit: int,
        days: int,
        end_date: date | None = None,
        periodic_only: bool = False,
    ) -> list[dict[str, Any]]:
        end_date = end_date or date.today()
        start_date = end_date - timedelta(days=days)
        filings: list[dict[str, Any]] = []
        page_no = 1
        while len(filings) < limit:
            response = self._get(
                f"{self.BASE_URL}/list.json",
                params={
                    "crtfc_key": self.api_key,
                    "corp_code": corp_code,
                    "bgn_de": start_date.strftime("%Y%m%d"),
                    "end_de": end_date.strftime("%Y%m%d"),
                    "last_reprt_at": "Y",
                    **({"pblntf_ty": "A"} if periodic_only else {}),
                    "page_count": 100,
                    "page_no": page_no,
                },
            )
            try:
                payload = response.json()
            except requests.JSONDecodeError as error:
                raise RuntimeError("Open DART 공시 목록 응답이 JSON이 아닙니다.") from error
            status = str(payload.get("status", ""))
            if status == "013":
                break
            if status != "000":
                raise RuntimeError(
                    f"Open DART 오류 {status}: {payload.get('message', '알 수 없음')}"
                )
            page = payload.get("list", [])
            if not isinstance(page, list) or not page:
                break
            if periodic_only and any(str(row.get("corp_code", "")) != corp_code for row in page):
                raise RuntimeError("공시 목록의 기업 식별자가 일치하지 않습니다.")
            filings.extend(page)
            if page_no >= int(payload.get("total_page", page_no)):
                break
            page_no += 1
        return filings[:limit]

    def _download_original(self, receipt_no: str) -> bytes:
        response = self._get(
            f"{self.BASE_URL}/document.xml",
            params={"crtfc_key": self.api_key, "rcept_no": receipt_no},
        )
        content = response.content
        if len(content) > self.MAX_ORIGINAL_BYTES:
            raise ValueError("Open DART 원문이 50MB를 초과합니다.")
        if not zipfile.is_zipfile(io.BytesIO(content)):
            raise RuntimeError("Open DART 원문 응답이 ZIP 파일이 아닙니다.")
        return content

    def _get(self, url: str, params: dict[str, Any]) -> requests.Response:
        try:
            response = self.session.get(
                url,
                params=params,
                timeout=self.TIMEOUT,
            )
            response.raise_for_status()
            return response
        except requests.RequestException as error:
            raise RuntimeError("Open DART API 요청에 실패했습니다.") from error

    @staticmethod
    def _safe_name(value: str) -> str:
        return re.sub(r"[^0-9A-Za-z가-힣._-]+", "_", value).strip("_") or "company"
