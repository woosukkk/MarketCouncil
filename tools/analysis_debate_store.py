import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


class AnalysisDebateStore:
    def __init__(
        self,
        base_dir: Path = Path("results/analysis_debate"),
    ) -> None:
        self.base_dir = base_dir

    def save(
        self,
        company_name: str,
        debate: dict[str, Any],
    ) -> str:
        save_dir = self._company_dir(company_name)
        save_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = save_dir / f"analysis_debate_{timestamp}.json"
        payload = {
            "company_name": company_name,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            **debate,
        }
        file_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return str(file_path)

    def load_latest(self, company_name: str) -> dict[str, Any] | None:
        save_dir = self._company_dir(company_name)
        if not save_dir.exists():
            return None
        files = sorted(
            save_dir.glob("analysis_debate_*.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if not files:
            return None
        latest_path = files[0]
        try:
            result = json.loads(latest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(
                f"최근 토론 결과를 읽지 못했습니다: {latest_path}"
            ) from error
        if not isinstance(result, dict):
            raise ValueError("최근 토론 결과가 JSON 객체가 아닙니다.")
        result["_source_path"] = str(latest_path)
        return result

    def _company_dir(self, company_name: str) -> Path:
        safe_company = re.sub(
            r"[^0-9A-Za-z가-힣._-]+",
            "_",
            company_name,
        ).strip("_") or "company"
        return self.base_dir / safe_company
