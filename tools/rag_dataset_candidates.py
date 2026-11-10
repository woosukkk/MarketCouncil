"""List indexed documents as gold-label candidates for the RAG benchmark.

Reads only documents/registry.json. No model, network or LLM call is made.
A person still writes each question and chooses which source answers it;
this tool only shows which `source` values exist for a company and date.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

FIELDS = ("source", "company", "published_at", "source_type", "title", "fiscal_period")


def load_records(registry_path: Path) -> list[dict[str, Any]]:
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    records = data.values() if isinstance(data, dict) else data
    return [record for record in records if isinstance(record, dict)]


def candidates(
    records: list[dict[str, Any]],
    company: str | None = None,
    as_of_date: str | None = None,
) -> list[dict[str, str]]:
    rows = []
    for record in records:
        if record.get("status") != "ingested" or not record.get("indexed_at"):
            continue
        if company and record.get("company") != company:
            continue
        published = str(record.get("published_at") or "")[:10]
        if as_of_date and (not published or published > as_of_date):
            continue  # unknown or future dates cannot be gold evidence for this cutoff
        rows.append({
            "source": str(record.get("filename") or Path(str(record.get("file_path", ""))).name),
            "company": str(record.get("company") or ""),
            "published_at": published,
            "source_type": str(record.get("source_type") or ""),
            "title": str(record.get("title") or ""),
            "fiscal_period": str(record.get("fiscal_period") or ""),
        })
    return sorted(rows, key=lambda row: (row["company"], row["published_at"], row["source"]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RAG 정답 후보 문서 목록 (모델·네트워크 호출 없음)")
    parser.add_argument("--registry", type=Path, default=Path("documents/registry.json"))
    parser.add_argument("--company")
    parser.add_argument("--as-of-date", help="YYYY-MM-DD; 이후 발행 문서와 날짜 미상 문서는 제외")
    parser.add_argument("--output", type=Path, help="CSV 저장 경로 (생략 시 표준 출력)")
    args = parser.parse_args(argv)
    rows = candidates(load_records(args.registry), args.company, args.as_of_date)
    if args.output:
        if args.output.exists():
            raise SystemExit(f"이미 있는 파일은 덮어쓰지 않습니다: {args.output}")
        handle = args.output.open("w", encoding="utf-8-sig", newline="")
    else:
        handle = sys.stdout
    writer = csv.DictWriter(handle, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    if args.output:
        handle.close()
    print(f"{len(rows)}개 후보", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
