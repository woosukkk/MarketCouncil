"""Metadata-only Ragas result import. Does not execute or certify evaluations."""
import csv
import hashlib
import json
import math
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

METRICS = ('faithfulness', 'context_precision', 'context_recall', 'factual_correctness')
TOKEN = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:/ +@-]{0,119}\Z')
HASH = re.compile(r'[a-f0-9]{64}\Z')
SETTINGS = ('framework_version', 'dataset_name', 'dataset_version', 'evaluator_model', 'reference_origin', 'metric_config_hash')


def validate_report(raw: dict) -> dict:
    def fail() -> None:
        raise ValueError('외부 평가 기록의 형식·조건·사례별 점수를 확인하세요.')

    if not isinstance(raw, dict) or raw.get('schema_version') != 1 or raw.get('kind') != 'rag' or raw.get('scope') != 'external_rag' or raw.get('status') != 'success':
        fail()
    try:
        if str(uuid.UUID(raw['id'])) != raw['id']:
            fail()
        stamp = datetime.fromisoformat(raw['recorded_at'].replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            fail()
    except (ValueError, KeyError, AttributeError, TypeError):
        fail()
    settings = raw.get('settings')
    if not isinstance(settings, dict) or set(settings) != set(SETTINGS) or any(not isinstance(settings[k], str) or not TOKEN.fullmatch(settings[k]) for k in SETTINGS):
        fail()
    if settings['reference_origin'] not in ('human', 'mixed', 'synthetic') or not HASH.fullmatch(settings['metric_config_hash']) or not isinstance(raw.get('dataset_hash'), str) or not HASH.fullmatch(raw['dataset_hash']):
        fail()
    rows = raw.get('cases')
    if not isinstance(rows, list) or not 1 <= len(rows) <= 1000:
        fail()
    seen = set()
    clean = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'case_id', *METRICS} or not isinstance(row['case_id'], str) or not re.fullmatch(r'[a-f0-9]{16}', row['case_id']) or row['case_id'] in seen:
            fail()
        seen.add(row['case_id'])
        for key in METRICS:
            value = row[key]
            if value is not None and (type(value) not in (float, int) or not math.isfinite(value) or not 0 <= value <= 1):
                fail()
        clean.append({k: row[k] for k in ('case_id', *METRICS)})
    metrics = {'case_count': len(rows)}
    for key in METRICS:
        values = [row[key] for row in rows if row[key] is not None]
        metrics[key] = sum(values) / len(values) if values else None
        metrics[key + '_count'] = len(values)
    if not any(metrics[k + '_count'] for k in METRICS):
        fail()
    supplied = raw.get('metrics')
    if not isinstance(supplied, dict) or set(supplied) != set(metrics):
        fail()
    for key, expected in metrics.items():
        actual = supplied[key]
        if expected is None:
            if actual is not None:
                fail()
        elif type(actual) not in (int, float) or not math.isfinite(actual) or not math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-9):
            fail()
    return {'schema_version': 1, 'kind': 'rag', 'scope': 'external_rag', 'status': 'success', 'id': raw['id'], 'recorded_at': stamp.isoformat(), 'label': 'Ragas · imported results', 'version': settings['framework_version'], 'dataset_hash': raw['dataset_hash'], 'settings': dict(settings), 'metrics': metrics, 'cases': clean}


def import_scores(scores: Path, manifest: Path) -> dict:
    if scores.stat().st_size > 5 * 1024 * 1024 or manifest.stat().st_size > 16384:
        raise ValueError('평가 CSV는 5MB, 설정 JSON은 16KB 이하로 준비하세요.')
    config = json.loads(manifest.read_text(encoding='utf-8-sig'))
    if not isinstance(config, dict) or set(config) != {*SETTINGS, 'dataset_hash'}:
        raise ValueError('설정 JSON의 필수 항목을 확인하세요.')
    rows = []
    with scores.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or 'case_id' not in reader.fieldnames or not set(reader.fieldnames).intersection(METRICS) or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError('case_id와 Ragas 점수 열이 필요합니다.')
        for row in reader:
            if len(rows) >= 1000 or not row.get('case_id'):
                raise ValueError('사례는 고유 ID를 포함해 최대 1000개입니다.')
            item = {'case_id': hashlib.sha256(row['case_id'].encode()).hexdigest()[:16]}
            for key in METRICS:
                value = row.get(key, '').strip()
                item[key] = None if value.lower() in ('', 'nan', 'null') else float(value)
            rows.append(item)
    metrics = {'case_count': len(rows)}
    for key in METRICS:
        values = [row[key] for row in rows if row[key] is not None]
        metrics[key] = sum(values) / len(values) if values else None
        metrics[key + '_count'] = len(values)
    return validate_report({'schema_version': 1, 'kind': 'rag', 'scope': 'external_rag', 'status': 'success', 'id': str(uuid.uuid4()), 'recorded_at': datetime.now(timezone.utc).isoformat(), 'dataset_hash': config['dataset_hash'], 'settings': {k: config[k] for k in SETTINGS}, 'metrics': metrics, 'cases': rows})


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description='Ragas 사례별 CSV를 관리자용 원문 없는 기록으로 변환합니다. 평가나 API 호출은 하지 않습니다.')
    parser.add_argument('scores', type=Path)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        report = import_scores(args.scores, args.manifest)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(report, stream, ensure_ascii=False, allow_nan=False)
    except (OSError, ValueError, TypeError, KeyError, csv.Error):
        parser.exit(1, '변환 실패: 입력 형식·점수 범위와 새 출력 경로를 확인하세요.\n')
    print('관리자용 Ragas 기록을 저장했습니다. 원문은 포함하지 않습니다.')


if __name__ == '__main__':
    main()
