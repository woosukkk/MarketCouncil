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
        safe_company = re.sub(
            r"[^0-9A-Za-z가-힣._-]+",
            "_",
            company_name,
        ).strip("_") or "company"
        save_dir = self.base_dir / safe_company
        save_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = save_dir / f"analysis_debate_{timestamp}.json"
        payload = {
            "company_name": company_name,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "bull_rebuttal": debate.get("bull_rebuttal", ""),
            "bear_rebuttal": debate.get("bear_rebuttal", ""),
            "included_in_judge": False,
        }
        file_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return str(file_path)
