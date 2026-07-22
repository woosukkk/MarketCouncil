import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


class VideoDebateStore:
    def __init__(self, base_dir: Path = Path("results/video_debate")) -> None:
        self.base_dir = base_dir

    def save(
        self,
        company_name: str,
        result: dict[str, Any],
    ) -> str:
        created_at = datetime.now().astimezone().isoformat(
            timespec="seconds"
        )
        save_dir = self.base_dir / self._safe_company_name(company_name)
        save_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = save_dir / f"video_debate_{timestamp}.json"
        payload = {
            "company_name": company_name,
            "created_at": created_at,
            **result,
        }
        file_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return str(file_path)

    def load_latest(self, company_name: str) -> dict[str, Any] | None:
        save_dir = self.base_dir / self._safe_company_name(company_name)
        files = sorted(save_dir.glob("video_debate_*.json"), reverse=True)
        if not files:
            return None

        try:
            data = json.loads(files[0].read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as error:
            raise ValueError("최신 영상 토론 결과를 읽을 수 없습니다.") from error

        if not isinstance(data, dict):
            raise ValueError("영상 토론 결과 형식이 올바르지 않습니다.")
        return data

    @staticmethod
    def _safe_company_name(company_name: str) -> str:
        safe_name = re.sub(
            r"[^0-9A-Za-z가-힣._-]+",
            "_",
            company_name.strip(),
        ).strip("._")
        if not safe_name:
            raise ValueError("올바른 기업명을 입력하세요.")
        return safe_name
