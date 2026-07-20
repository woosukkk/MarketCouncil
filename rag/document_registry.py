import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


DOCUMENTS_DIR = Path("documents")
INBOX_DIR = DOCUMENTS_DIR / "inbox"
APPROVED_DIR = DOCUMENTS_DIR / "approved"
REJECTED_DIR = DOCUMENTS_DIR / "rejected"
REGISTRY_PATH = DOCUMENTS_DIR / "registry.json"
TIMEZONE = "Asia/Seoul"


class DocumentRegistry:
    def __init__(self, registry_path: Path = REGISTRY_PATH) -> None:
        self.registry_path = registry_path
        self.ensure_directories()

    @staticmethod
    def ensure_directories() -> None:
        for directory in (INBOX_DIR, APPROVED_DIR, REJECTED_DIR):
            directory.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, dict[str, Any]]:
        if not self.registry_path.exists():
            return {}

        try:
            data = json.loads(
                self.registry_path.read_text(encoding="utf-8")
            )
        except (json.JSONDecodeError, OSError) as error:
            raise ValueError("문서 등록부를 읽을 수 없습니다.") from error

        if not isinstance(data, dict):
            raise ValueError("문서 등록부 형식이 올바르지 않습니다.")

        return data

    def save(self, records: dict[str, dict[str, Any]]) -> None:
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.registry_path.with_suffix(".tmp")
        temporary_path.write_text(
            json.dumps(records, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary_path.replace(self.registry_path)

    def find_by_hash(self, content_hash: str) -> dict[str, Any] | None:
        return self.load().get(content_hash)

    def upsert(self, record: dict[str, Any]) -> dict[str, Any]:
        content_hash = str(record["content_hash"])
        records = self.load()
        records[content_hash] = record
        self.save(records)
        return record

    def update(
        self,
        content_hash: str,
        **changes: Any,
    ) -> dict[str, Any]:
        records = self.load()
        if content_hash not in records:
            raise KeyError("등록되지 않은 문서입니다.")

        records[content_hash].update(changes)
        self.save(records)
        return records[content_hash]

    @staticmethod
    def file_hash(file_path: Path) -> str:
        digest = hashlib.sha256()
        with file_path.open("rb") as file:
            for block in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def now() -> str:
        return datetime.now(
            ZoneInfo(TIMEZONE)
        ).isoformat(timespec="seconds")

    @staticmethod
    def unique_destination(directory: Path, filename: str) -> Path:
        destination = directory / filename
        if not destination.exists():
            return destination

        stem = Path(filename).stem
        suffix = Path(filename).suffix
        index = 1
        while destination.exists():
            destination = directory / f"{stem}_{index}{suffix}"
            index += 1
        return destination
