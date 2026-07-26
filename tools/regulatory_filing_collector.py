import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from tools.dart_collector import DartCollector
from tools.sec_edgar_collector import SecEdgarCollector


load_dotenv()


class RegulatoryFilingCollector:
    def __init__(self, base_dir: Path = Path("documents/regulatory")) -> None:
        self.base_dir = base_dir

    def collect(
        self,
        market: str,
        company_name: str,
        ticker: str,
        limit: int = 10,
    ) -> dict[str, Any]:
        normalized_market = market.strip().lower()
        if normalized_market in {"kr", "korea", "dart"}:
            return DartCollector(
                api_key=os.getenv("DART_API_KEY", ""),
                base_dir=self.base_dir,
            ).collect(company_name, ticker, limit)
        if normalized_market in {"us", "usa", "sec"}:
            return SecEdgarCollector(
                user_agent=os.getenv("SEC_USER_AGENT", ""),
                base_dir=self.base_dir,
            ).collect(company_name, ticker, limit)
        raise ValueError("시장은 kr 또는 us로 입력하세요.")
