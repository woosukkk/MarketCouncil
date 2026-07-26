import json
import re
from pathlib import Path
from typing import Any

import requests


class SecEdgarCollector:
    TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
    SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
    ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data"
    SUPPORTED_FORMS = {"10-K", "10-Q", "8-K", "20-F", "40-F", "6-K"}
    TIMEOUT = (5, 30)
    MAX_ORIGINAL_BYTES = 50 * 1024 * 1024

    def __init__(self, user_agent: str, base_dir: Path) -> None:
        if not user_agent or "@" not in user_agent:
            raise ValueError(
                "SEC_USER_AGENT에 프로젝트명과 연락 가능한 이메일을 입력하세요."
            )
        self.base_dir = base_dir
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate",
        })

    def collect(
        self,
        company_name: str,
        ticker: str,
        limit: int = 10,
    ) -> dict[str, Any]:
        cik = self._resolve_cik(ticker)
        filings = self._list_filings(cik, limit)
        target_dir = self.base_dir / "sec" / self._safe_name(company_name)
        target_dir.mkdir(parents=True, exist_ok=True)

        downloaded: list[dict[str, Any]] = []
        skipped: list[dict[str, str]] = []
        failed: list[dict[str, str]] = []

        for filing in filings:
            accession = filing["accession_number"]
            primary_document = filing["primary_document"]
            extension = Path(primary_document).suffix.lower() or ".html"
            original_path = target_dir / f"{accession}{extension}"
            metadata_path = target_dir / f"{accession}.metadata.json"
            if original_path.exists() and metadata_path.exists():
                skipped.append({"id": accession, "reason": "already_downloaded"})
                continue

            source_url = self._filing_url(cik, accession, primary_document)
            try:
                content = self._get(source_url).content
                if len(content) > self.MAX_ORIGINAL_BYTES:
                    raise ValueError("SEC EDGAR 원문이 50MB를 초과합니다.")
                original_path.write_bytes(content)
                metadata = {
                    "provider": "sec_edgar",
                    "company": company_name,
                    "ticker": ticker.upper(),
                    "cik": cik,
                    "filing_id": accession,
                    "form_type": filing["form"],
                    "title": f"{company_name} {filing['form']}",
                    "filed_at": filing["filing_date"],
                    "report_date": filing["report_date"],
                    "publisher": "U.S. Securities and Exchange Commission",
                    "source_url": source_url,
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
                failed.append({"id": accession, "reason": str(error)})

        return {
            "provider": "sec_edgar",
            "downloaded": downloaded,
            "skipped": skipped,
            "failed": failed,
        }

    def _resolve_cik(self, ticker: str) -> str:
        payload = self._get(self.TICKERS_URL).json()
        normalized_ticker = ticker.strip().upper()
        for company in payload.values():
            if str(company.get("ticker", "")).upper() == normalized_ticker:
                return str(company["cik_str"]).zfill(10)
        raise ValueError("SEC EDGAR에서 티커에 해당하는 CIK를 찾지 못했습니다.")

    def _list_filings(self, cik: str, limit: int) -> list[dict[str, str]]:
        payload = self._get(self.SUBMISSIONS_URL.format(cik=cik)).json()
        recent = payload.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        accessions = recent.get("accessionNumber", [])
        filing_dates = recent.get("filingDate", [])
        report_dates = recent.get("reportDate", [])
        primary_documents = recent.get("primaryDocument", [])

        filings: list[dict[str, str]] = []
        for form, accession, filing_date, report_date, primary_document in zip(
            forms,
            accessions,
            filing_dates,
            report_dates,
            primary_documents,
        ):
            if form not in self.SUPPORTED_FORMS or not primary_document:
                continue
            filings.append({
                "form": form,
                "accession_number": accession,
                "filing_date": filing_date,
                "report_date": report_date,
                "primary_document": primary_document,
            })
            if len(filings) >= limit:
                break
        return filings

    def _get(self, url: str) -> requests.Response:
        try:
            response = self.session.get(url, timeout=self.TIMEOUT)
            response.raise_for_status()
            return response
        except requests.RequestException as error:
            raise RuntimeError("SEC EDGAR API 요청에 실패했습니다.") from error

    @classmethod
    def _filing_url(
        cls,
        cik: str,
        accession: str,
        primary_document: str,
    ) -> str:
        cik_without_zeros = str(int(cik))
        accession_compact = accession.replace("-", "")
        return (
            f"{cls.ARCHIVES_URL}/{cik_without_zeros}/"
            f"{accession_compact}/{primary_document}"
        )

    @staticmethod
    def _safe_name(value: str) -> str:
        return re.sub(r"[^0-9A-Za-z가-힣._-]+", "_", value).strip("_") or "company"
