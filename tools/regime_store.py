import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


class RegimeStore:
    def __init__(self, base_dir: Path = Path("results/regime_analysis")) -> None:
        self.base_dir = base_dir

    def save(self, company_name: str, analysis: dict[str, Any]) -> str:
        company_dir = self.base_dir / self._safe_name(company_name)
        company_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = company_dir / f"regime_analysis_{timestamp}.json"
        path.write_text(
            json.dumps(analysis, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        return str(path)

    def load_latest(self, company_name: str) -> dict[str, Any] | None:
        company_dir = self.base_dir / self._safe_name(company_name)
        files = sorted(company_dir.glob("regime_analysis_*.json"), reverse=True)
        if not files:
            return None
        try:
            result = json.loads(files[0].read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"국면 분석 파일을 읽을 수 없습니다: {files[0]}") from error
        if not isinstance(result, dict):
            raise ValueError("국면 분석 결과는 JSON 객체여야 합니다.")
        return result

    @staticmethod
    def _safe_name(value: str) -> str:
        return re.sub(r"[^0-9A-Za-z가-힣_-]+", "_", value).strip("_") or "company"
