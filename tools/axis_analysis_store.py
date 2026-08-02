import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


class AxisAnalysisStore:
    def __init__(self, base_dir: Path = Path("results/axis_analysis")) -> None:
        self.base_dir = base_dir

    def save(self, company_name: str, analysis: dict[str, Any]) -> str:
        save_dir = self._company_dir(company_name)
        save_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = save_dir / f"axis_analysis_{timestamp}.json"
        payload = {
            "company_name": company_name,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            **analysis,
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        return str(path)

    def load_latest(self, company_name: str) -> dict[str, Any] | None:
        save_dir = self._company_dir(company_name)
        if not save_dir.exists():
            return None
        paths = sorted(
            save_dir.glob("axis_analysis_*.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if not paths:
            return None
        try:
            result = json.loads(paths[0].read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"최근 축 분석을 읽지 못했습니다: {paths[0]}") from error
        if not isinstance(result, dict):
            raise ValueError("최근 축 분석 결과가 JSON 객체가 아닙니다.")
        return result

    def _company_dir(self, company_name: str) -> Path:
        safe_name = re.sub(
            r"[^0-9A-Za-z가-힣._-]+", "_", company_name
        ).strip("_") or "company"
        return self.base_dir / safe_name
