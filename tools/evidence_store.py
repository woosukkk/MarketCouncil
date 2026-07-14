import json
from datetime import datetime
from pathlib import Path
from typing import Any


class EvidenceStore:
    def __init__(self, base_dir: str = "evidence") -> None:
        self.base_dir = Path(base_dir)

    def save(
        self,
        company_name: str,
        perspective: str,
        evidence_data: dict[str, Any],
    ) -> str:
        save_dir = (
            self.base_dir
            / perspective.lower()
            / company_name
        )
        save_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = save_dir / f"{timestamp}.json"

        payload = {
            "company_name": company_name,
            "perspective": perspective.lower(),
            "searched_at": datetime.now().isoformat(
                timespec="seconds"
            ),
            **evidence_data,
        }

        file_path.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return str(file_path)

    def load_latest(
        self,
        company_name: str,
        perspective: str,
    ) -> dict[str, Any] | None:
        save_dir = (
            self.base_dir
            / perspective.lower()
            / company_name
        )

        if not save_dir.exists():
            return None

        files = sorted(
            save_dir.glob("*.json"),
            reverse=True,
        )

        if not files:
            return None

        return json.loads(
            files[0].read_text(encoding="utf-8")
        )

    def load_all(
        self,
        company_name: str,
        perspective: str,
    ) -> list[dict[str, Any]]:
        save_dir = (
            self.base_dir
            / perspective.lower()
            / company_name
        )

        if not save_dir.exists():
            return []

        results = []

        for file_path in sorted(save_dir.glob("*.json")):
            data = json.loads(
                file_path.read_text(encoding="utf-8")
            )
            results.append(data)

        return results