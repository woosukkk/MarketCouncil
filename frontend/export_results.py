"""Export the public result snapshot; never copy credentials, models or local paths."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / "results" / "analysis_debate"
PUBLIC_MANIFEST = ROOT.parent / "public-results.json"
FIELDS = ("company_name", "created_at", "financial_data", "agenda", "rounds", "issue_statuses", "moderator_summary", "navigation", "bull_analysis", "bear_analysis")


EVIDENCE_FIELDS = ("evidence_id", "source_id", "exact_quote", "reason", "verified", "title", "source_type", "source_url", "published_at", "page_number", "source_page_url")


def compact_evidence(value: object) -> object:
    """Keep cited excerpts and source metadata; retrieval context stays local."""
    if isinstance(value, list):
        return [compact_evidence(item) for item in value]
    if isinstance(value, dict):
        return {
            key: [
                {field: item[field] for field in EVIDENCE_FIELDS if field in item}
                if isinstance(item, dict) else item
                for item in child
            ] if key == "evidence" and isinstance(child, list) else compact_evidence(child)
            for key, child in value.items()
        }
    return value


def selected_results(manifest: Path) -> list[tuple[Path, dict]]:
    """Require approval of exact result bytes, never discover files automatically."""
    try:
        entries = json.loads(manifest.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as error:
        raise ValueError("An explicit public-results manifest is required; see docs/result-publishing.md") from error
    if not isinstance(entries, dict) or set(entries) != {"results"} or not isinstance(entries["results"], list) or not entries["results"]:
        raise ValueError("Public manifest must contain a non-empty results list")
    source = SOURCE.resolve()
    selected = []
    seen = set()
    for entry in entries["results"]:
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
            raise ValueError("Each public result requires path and sha256")
        relative, digest = entry["path"], entry["sha256"]
        if not isinstance(relative, str) or "\\" in relative or any(part in ("", ".", "..") for part in relative.split("/")) or Path(relative).is_absolute():
            raise ValueError("Public result path must be relative to the analysis archive")
        if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ValueError("Public result sha256 must be 64 lowercase hexadecimal characters")
        path = (source / relative).resolve()
        if not path.is_relative_to(source) or not path.name.startswith("analysis_debate_") or path.suffix != ".json" or not path.is_file() or path in seen:
            raise ValueError("Public manifest contains an invalid or duplicate result path")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("A selected result changed after public approval; review it and update its manifest hash")
        selected.append((path, json.loads(raw.decode("utf-8-sig"))))
        seen.add(path)
    return sorted(selected, key=lambda item: str(item[0]))


def export(manifest: Path | None = None) -> None:
    output = ROOT / "public" / "data"
    records = []
    payloads = {}
    for path, data in selected_results(manifest if manifest is not None else PUBLIC_MANIFEST):
        if not isinstance(data, dict) or not isinstance(data.get("company_name"), str):
            raise ValueError(f"Invalid analysis result: {path.name}")
        identifier = hashlib.sha256(str(path.relative_to(SOURCE.resolve())).encode()).hexdigest()[:16]
        payloads[identifier] = compact_evidence({key: data[key] for key in FIELDS if key in data})
        for side in ("bull", "bear"):
            if not data.get(f"{side}_analysis") and isinstance(data.get(f"{side}_rebuttal"), str):
                payloads[identifier][f"{side}_analysis"] = data[f"{side}_rebuttal"]
        records.append({"id": identifier, "company_name": data["company_name"], "created_at": data.get("created_at", ""), "ticker": data.get("financial_data", {}).get("ticker", ""), "summary": data.get("moderator_summary", {}).get("summary", ""), "issue_count": len(data.get("agenda", [])), "round_count": len(data.get("rounds", []))})
    if not records:
        raise ValueError("No saved analysis results found")
    output.mkdir(parents=True, exist_ok=True)
    # Only selected result fields are exported; original documents and vectors stay local.
    for identifier, payload in payloads.items():
        (output / f"{identifier}.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    records.sort(key=lambda row: row["created_at"], reverse=True)
    temporary = output / "index.json.tmp"
    temporary.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
    temporary.replace(output / "index.json")
    print(f"Exported {len(records)} public result snapshots")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Export only explicitly approved public results")
    parser.add_argument("--manifest", type=Path, default=PUBLIC_MANIFEST)
    export(parser.parse_args().manifest)
