"""Collect or audit primary evidence without loading AI models or Chroma."""
import argparse
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.evidence_preflight import evidence_base, prepare_company
from tools.company_profiles import PROFILES, get_profile


def inventory(root: Path) -> dict:
    """Registry/file presence only; do not imply vector indexing or retrieval quality."""
    registry = root/'documents/registry.json'
    result = {'registered': 0, 'files_present': 0, 'companies': {}, 'vector_index': 'not_measured'}
    if not registry.is_file():
        return result
    if registry.stat().st_size > 10_000_000:
        return {**result, 'error': 'registry_too_large'}
    try:
        rows = json.loads(registry.read_text(encoding='utf-8-sig'))
        if not isinstance(rows, dict) or len(rows) > 10000:
            raise ValueError()
        for row in rows.values():
            if not isinstance(row, dict):
                continue
            company = row.get('company', '')
            if not isinstance(company, str) or not 1 <= len(company) <= 120:
                continue
            result['registered'] += 1
            result['companies'][company] = result['companies'].get(company, 0)+1
            value = row.get('file_path')
            if isinstance(value, str):
                path = Path(value)
                path = (path if path.is_absolute() else root/path).resolve()
                if path.is_relative_to(root.resolve()) and path.is_file():
                    result['files_present'] += 1
    except (OSError, ValueError, TypeError):
        result['error'] = 'invalid_registry'
    return result


def run(*, base_dir: Path | None = None, refresh: bool = False,
        company: str | None = None, ticker: str | None = None) -> dict:
    start = time.perf_counter()
    base = evidence_base(base_dir)
    profiles = [get_profile(company, ticker)] if company and ticker else PROFILES
    reports, failures = [], []
    for profile in profiles:
        manifest, report = prepare_company(profile['company_name'], profile['ticker'], refresh=refresh, base_dir=base)
        reports.append(report)
        for item in manifest.get('failures', []):
            code = item.get('code')
            allowed = {'manifest_missing','invalid_manifest','download_failed','source_unavailable',
                       'date_unavailable','body_unavailable','issuer_mismatch','cache_invalid'}
            failures.append({'ticker': profile['ticker'], 'code': code if code in allowed else 'collection_failed'})
    return {'schema_version': 1, 'kind': 'monitoring', 'scope': 'evidence_readiness',
            'id': str(uuid.uuid4()), 'recorded_at': datetime.now(timezone.utc).isoformat(),
            'label': 'Company evidence readiness', 'version': 'primary-v1', 'status': 'success',
            'metrics': {'duration_ms': round((time.perf_counter()-start)*1000, 3)},
            'settings': {'case_count': len(reports)}, 'companies': reports,
            'collection_failures': failures[:100]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true', help='Fetch original filings/IR; never call an LLM')
    parser.add_argument('--company')
    parser.add_argument('--ticker')
    parser.add_argument('--base-dir', type=Path)
    parser.add_argument('--output', type=Path, default=Path('evidence-readiness.json'))
    args = parser.parse_args()
    if bool(args.company) != bool(args.ticker):
        parser.error('--company and --ticker must be provided together')
    report = run(base_dir=args.base_dir, refresh=args.refresh, company=args.company, ticker=args.ticker)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    repo = Path(__file__).resolve().parent.parent
    local = {'source_registry': inventory(repo), 'vector_retrieval_quality': 'not_measured'}
    args.output.with_suffix('.inventory.json').write_text(json.dumps(local, ensure_ascii=False, indent=2), encoding='utf-8')
    for item in report['companies']:
        print(json.dumps({key: item[key] for key in ('company_name','ticker','status','counts','missing')}, ensure_ascii=False))
    print('Saved metadata-only readiness report; no AI analysis, upload or publication was executed.')


if __name__ == '__main__':
    main()
