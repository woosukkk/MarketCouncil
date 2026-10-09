"""Local-only Supabase publisher. Upload immutable documents before replacing the index."""
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent


def publish_results() -> int:
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env.result-upload')
    base = os.environ.get('RESULTS_SUPABASE_URL', '').rstrip('/')
    key = os.environ.get('RESULTS_SUPABASE_SECRET_KEY', '')
    bucket = os.environ.get('RESULTS_STORAGE_BUCKET', 'analysis-results')
    if not re.fullmatch(r'https://[a-z0-9-]+\.supabase\.co', base) or not key:
        raise ValueError('Set RESULTS_SUPABASE_URL and RESULTS_SUPABASE_SECRET_KEY in .env.result-upload')
    if not re.fullmatch(r'[a-z0-9-]+', bucket):
        raise ValueError('Invalid storage bucket name')
    from frontend.export_results import export
    export()
    directory = ROOT / 'frontend' / 'public' / 'data'
    records = json.loads((directory / 'index.json').read_text(encoding='utf-8'))

    def upload(name: str, content: bytes) -> None:
        request = urllib.request.Request(
            f'{base}/storage/v1/object/{bucket}/{quote(name, safe="/")}',
            data=content, method='POST',
            headers={'apikey': key, **({'Authorization': f'Bearer {key}'} if key.startswith('eyJ') else {}),
                     'Content-Type': 'application/json', 'x-upsert': 'true', 'Cache-Control': 'max-age=0'},
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                if response.status not in (200, 201):
                    raise RuntimeError('Unexpected storage response')
        except urllib.error.HTTPError as error:
            raise RuntimeError(f'Result upload failed (HTTP {error.code}); existing published index is retained unless the final index upload succeeded.') from None
        except (urllib.error.URLError, TimeoutError):
            raise RuntimeError('Result upload could not be confirmed. Local results are safe; retry publishing.') from None

    publish_snapshot(records, directory, upload)
    return len(records)


def publish_snapshot(records: list[dict], directory: Path, upload: Callable[[str, bytes], None]) -> None:
    published = []
    for record in records:
        identifier = record['id']
        if not re.fullmatch(r'[a-f0-9]{16}', identifier):
            raise ValueError('Invalid result identifier')
        content = (directory / f'{identifier}.json').read_bytes()
        # Content-addressed files keep the old index valid if an upload is interrupted.
        versioned = f'{identifier}-{hashlib.sha256(content).hexdigest()[:16]}'
        upload(f'{versioned}.json', content)
        published.append({**record, 'id': versioned})
    upload('index.json', json.dumps(published, ensure_ascii=False).encode('utf-8'))


if __name__ == '__main__':
    print(f'Published {publish_results()} results')
