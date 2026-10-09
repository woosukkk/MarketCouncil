"""Export the public result snapshot; never copy credentials, models or local paths."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / "results" / "analysis_debate"
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


def export() -> None:
    output = ROOT / "public" / "data"
    records = []
    payloads = {}
    for path in sorted(SOURCE.rglob("analysis_debate_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("company_name"), str):
            raise ValueError(f"Invalid analysis result: {path.name}")
        identifier = hashlib.sha256(str(path.relative_to(SOURCE)).encode()).hexdigest()[:16]
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
    (output / "index.json").write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
    print(f"Exported {len(records)} public result snapshots")

if __name__ == "__main__":
    export()
