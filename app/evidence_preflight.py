"""Prepare and verify local primary evidence before any model call."""
import hashlib
import os
import re
from contextvars import ContextVar, Token
from contextlib import contextmanager
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from tools.company_evidence_collector import CompanyEvidenceCollector
from tools.company_profiles import get_profile
from tools.evidence_readiness import evaluate_readiness, validate_readiness_report


_BASE: ContextVar[Path | None] = ContextVar('company_evidence_base', default=None)
_BOUND: ContextVar[tuple[str, str] | None] = ContextVar('prepared_company_corpus', default=None)
_KST = timezone(timedelta(hours=9))


class EvidenceNotReady(ValueError):
    def __init__(self, report: dict[str, Any]) -> None:
        self.report = report
        super().__init__('공시·실적 발표 본문이 부족하거나 검증되지 않았습니다. 근거 준비·현황을 먼저 확인하세요.')


def evidence_base(base_dir: Path | None = None) -> Path:
    if base_dir is not None:
        path = Path(base_dir).resolve()
        _BASE.set(path)
        return path
    if _BASE.get() is not None:
        return _BASE.get()
    if os.environ.get('MARKETCOUNCIL_EVIDENCE_DIR'):
        return Path(os.environ['MARKETCOUNCIL_EVIDENCE_DIR']).resolve()
    if os.name == 'nt':
        return (Path(os.environ.get('LOCALAPPDATA', str(Path.home())))/'MarketCouncil/company-evidence').resolve()
    return Path('documents/company_evidence').resolve()


def _collection_settings() -> None:
    # Source runs can reuse configured provider credentials without importing model configuration.
    from dotenv import dotenv_values
    values = dotenv_values(Path(__file__).resolve().parent.parent/'.env')
    for key in ('DART_API_KEY', 'SEC_USER_AGENT'):
        if not os.environ.get(key) and values.get(key):
            os.environ[key] = values[key]


def prepare_company(company: str, ticker: str, *, refresh: bool = True,
                    base_dir: Path | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    profile = get_profile(company, ticker)
    base = evidence_base(base_dir)
    collector = CompanyEvidenceCollector(base)
    previous = collector.load(profile['company_name'], profile['ticker'])
    if refresh:
        _collection_settings()
        from tools.official_ir_collector import OfficialIRCollector
        manifest = collector.collect(profile['company_name'], profile['ticker'], limit=3)
        if profile['market'] == 'us' and manifest.get('latest_primary_failed'):
            from tools.issuer_filings_collector import IssuerFilingsCollector
            fallback = IssuerFilingsCollector(base).collect(profile['company_name'], profile['ticker'])
            manifest.update(documents=fallback['documents'], requested_ids=fallback['requested_ids'],
                            latest_required_ids=fallback['latest_required_ids'], primary_provider=fallback['primary_provider'],
                            latest_primary_failed=fallback['latest_primary_failed'],
                            failures=[*manifest.get('failures', []), *fallback['failures']])
        ir = OfficialIRCollector(base).collect(profile['company_name'], profile['ticker'],
                                             issuer_id=str(manifest.get('issuer_id', '')), limit=2)
        seen = set()
        documents = []
        for document in [*manifest['documents'], *ir['documents'],
                         *(doc for doc in previous['documents'] if doc.get('provider') == 'official_ir' and doc.get('document_type') == 'earnings')]:
            key = document['source_url']
            if key not in seen:
                documents.append(document)
                seen.add(key)
        manifest.update(documents=documents, failures=[*manifest.get('failures', []), *ir.get('failures', [])])
        manifest.setdefault('provider', profile['provider'])
        manifest.setdefault('issuer_id', profile.get('issuer_id') or '')
        manifest['collected_at'] = datetime.now(_KST).isoformat(timespec='seconds')
        manifest['latest_primary_failed'] = manifest.get('latest_primary_failed',
            any(item.get('stage') == 'collection' for item in manifest['failures']))
        manifest['latest_earnings_failed'] = bool(ir.get('latest_earnings_failed')) or not ir['documents']
        collector.save(manifest)
        # The cache schema deliberately stores document metadata, never a report's ready flag.
        # Re-read original/text bytes so validation and analysis use the same verified corpus.
        loaded = collector.load(profile['company_name'], profile['ticker'])
        loaded.update(latest_primary_failed=manifest['latest_primary_failed'],
                      latest_earnings_failed=manifest['latest_earnings_failed'])
        manifest = loaded
    else:
        manifest = previous
    evaluated = dict(manifest)
    if manifest.get('latest_primary_failed'):
        evaluated['documents'] = [doc for doc in manifest['documents'] if doc.get('document_type') == 'earnings']
    if manifest.get('latest_earnings_failed'):
        evaluated['documents'] = [doc for doc in evaluated['documents'] if doc.get('document_type') != 'earnings']
    return manifest, evaluate_readiness(evaluated)


def require_company_ready(company: str, ticker: str, *, refresh: bool = True,
                          base_dir: Path | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest, report = prepare_company(company, ticker, refresh=refresh, base_dir=base_dir)
    if report['status'] != 'ready':
        raise EvidenceNotReady(report)
    previous = _BOUND.get()
    if not refresh and previous and previous[0] == report['ticker'] and previous[1] != report['corpus_hash']:
        raise ValueError('분석 준비 이후 근거 묶음이 바뀌었습니다. 근거 준비를 다시 확인하세요.')
    return manifest, report


def bind_prepared_corpus(report: dict[str, Any]) -> Token[tuple[str, str] | None]:
    validate_readiness_report(report, report['company_name'], report['ticker'])
    return _BOUND.set((report['ticker'], report['corpus_hash']))


def reset_prepared_corpus(token: Token[tuple[str, str] | None]) -> None:
    _BOUND.reset(token)



@contextmanager
def prepared_corpus(report: dict[str, Any]) -> Iterator[None]:
    token = bind_prepared_corpus(report)
    try:
        yield
    finally:
        reset_prepared_corpus(token)


def assert_prepared_corpus(report: dict[str, Any]) -> None:
    previous = _BOUND.get()
    if previous and previous != (report['ticker'], report['corpus_hash']):
        raise ValueError('분석 준비 이후 근거 묶음이 바뀌었습니다. 이전 근거를 재사용하지 않습니다.')


def primary_chunks(manifest: dict[str, Any], report: dict[str, Any]) -> list[dict[str, Any]]:
    """Use bounded, literal primary-text excerpts; this is not vector retrieval."""
    validate_readiness_report(report, manifest['company_name'], manifest['ticker'])
    candidates = []
    for document in manifest['documents']:
        # Match the full normalized record, not just a body hash shared by different issuers.
        single = evaluate_readiness({**manifest, 'documents': [document]}, report['as_of_date'])
        if len(single['documents']) == 1 and single['documents'][0] in report['documents']:
            candidates.append(document)
    chosen = []
    for kind in ('annual', 'interim', 'earnings'):
        docs = [doc for doc in candidates if doc['document_type'] == kind]
        if docs:
            chosen.append(max(docs, key=lambda doc: (doc['report_date'], doc['published_at'])))
    chunks = []
    for document in chosen:
        text = document['content']
        starts = [0]
        for pattern in (r'매출|영업이익|revenue|operating income', r'위험|리스크|risk factor|liquidity'):
            match = re.search(pattern, text, re.I)
            if match and all(abs(match.start()-position) >= 2000 for position in starts):
                starts.append(max(0, match.start()-200))
        for index, start in enumerate(starts[:3]):
            content = text[start:start+2000]
            if not content:
                continue
            chunks.append({'text': content, 'source': document['source_url'],
                           'chunk_id': document['document_id']+'-'+str(index),
                           'metadata': {'company': manifest['company_name'], 'ticker': manifest['ticker'],
                                        'source_type': 'regulatory_filing' if document['provider'] != 'official_ir' else 'official',
                                        'source_url': document['source_url'],
                                        'title': manifest['company_name']+' '+document['document_type'],
                                        'published_at': document['published_at'], 'event_date': document['report_date'],
                                        'date_confidence': 'high', 'content_hash': document['content_hash']}})
    return chunks
