"""Original SEC-form copies linked by the issuer, without SEC access workarounds."""
import hashlib
import ipaddress
import json
import re
import socket
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zipfile import BadZipFile
from xml.etree.ElementTree import ParseError
from pypdf.errors import PyPdfError
from urllib.parse import parse_qs, urlencode, unquote, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from tools.company_evidence_collector import extract_official_text
from tools.company_profiles import get_profile

_KST = timezone(timedelta(hours=9))
_MAX_BYTES = 25 * 1024 * 1024


def _date(value: str) -> str:
    for fmt in ('%m/%d/%Y %H:%M:%S', '%B %d, %Y', '%b %d, %Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(value.strip(), fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError('issuer_filing_date_missing')


def _id(value: str) -> str:
    return 'ISSUER-' + hashlib.sha256(value.encode()).hexdigest()[:24]


class IssuerFilingsCollector:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = Path(base_dir).resolve()
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'MarketCouncil/1.0 issuer-evidence', 'Accept': 'text/html,application/json,*/*;q=0.8'})

    @staticmethod
    def _url(value: str, profile: dict[str, Any]) -> str:
        if not isinstance(value, str) or len(value) > 3000 or re.search(r'[\x00-\x20\x7f]', value):
            raise ValueError('invalid_issuer_url')
        source = urlsplit(value)
        path = unquote(source.path)
        if source.scheme != 'https' or source.username or source.password or source.port not in (None, 443) or '\\' in path or any(part in ('.', '..') for part in path.split('/')):
            raise ValueError('invalid_issuer_url')
        allowed = [*profile['ir_sources'], *profile.get('filing_sources', ())]
        permitted = any(source.hostname == item['host'] and any(path.casefold().startswith(prefix.casefold()) for prefix in item['path_prefixes']) for item in allowed)
        if profile['ticker'] == 'MSFT' and source.hostname == 'aka.ms':
            permitted = bool(re.fullmatch(r'/MSFT_FY\d{2}Q[1-4]_10[KQ]', path, re.I))
        if profile['ticker'] == 'MSFT' and source.hostname == 'view.officeapps.live.com' and path == '/op/view.aspx':
            target = parse_qs(source.query).get('src', [''])[0]
            return IssuerFilingsCollector._url(target, profile)
        if not permitted:
            raise ValueError('unverified_issuer_url')
        return urlunsplit(('https', source.hostname, source.path, source.query, ''))

    def _fetch(self, value: str, profile: dict[str, Any]) -> tuple[str, bytes]:
        url = self._url(value, profile)
        for _ in range(6):
            addresses = socket.getaddrinfo(urlsplit(url).hostname, 443, type=socket.SOCK_STREAM)
            if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
                raise ValueError('non_public_issuer_address')
            with self.session.get(url, stream=True, allow_redirects=False, timeout=(5, 25)) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    url = self._url(urljoin(url, response.headers.get('Location', '')), profile)
                    continue
                if response.status_code != 200:
                    raise ValueError('issuer_http_' + str(response.status_code))
                length = response.headers.get('Content-Length')
                if length and (not length.isdigit() or int(length) > _MAX_BYTES):
                    raise ValueError('issuer_file_too_large')
                raw = bytearray()
                for chunk in response.iter_content(65536):
                    raw.extend(chunk)
                    if len(raw) > _MAX_BYTES:
                        raise ValueError('issuer_file_too_large')
                return url, bytes(raw)
        raise ValueError('issuer_redirect_limit')

    def _list(self, profile: dict[str, Any]) -> list[dict[str, Any]]:
        page = profile['filing_index']
        _, raw = self._fetch(page, profile)
        html = raw.decode('utf-8', errors='replace')
        if profile['ticker'] == 'AAPL':
            key = re.search(r"var\s+Q4ApiKey\s*=\s*['\"]([A-Za-z0-9]+)['\"]", html)
            if not key or profile['sec_cik'] not in html:
                raise ValueError('issuer_feed_configuration_missing')
            groups = []
            for option in BeautifulSoup(html, 'html.parser').find_all('option', value=True):
                if re.search(r'annual filings|quarterly filings', option.get_text(' ', strip=True), re.I):
                    value = option['value']
                    if not re.fullmatch(r'\d+(?:,\d+)*', value):
                        raise ValueError('issuer_form_groups_invalid')
                    groups.extend(value.split(','))
            if not groups:
                raise ValueError('issuer_form_groups_missing')
            params = {'apiKey': key[1], 'LanguageId': 1, 'exchange': 'CIK', 'symbol': profile['sec_cik'],
                      'formGroupIdList': ','.join(dict.fromkeys(groups)), 'excludeNoDocuments': 'true', 'pageSize': 60, 'pageNumber': 0,
                      'tagList': '', 'includeTags': 'true', 'year': -1, 'excludeSelection': 1}
            _, body = self._fetch('https://investor.apple.com/feed/SECFiling.svc/GetEdgarFilingList?' + urlencode(params), profile)
            entries = json.loads(body).get('GetEdgarFilingListResult')
            if not isinstance(entries, list) or len(entries) > 60:
                raise ValueError('invalid_issuer_filing_list')
            selected = []
            for form, kind in (('10-K', 'annual'), ('10-Q', 'interim')):
                rows = sorted((row for row in entries if row.get('FilingTypeMnemonic') == form), key=lambda row: _date(row['FilingDate']), reverse=True)
                if rows:
                    row = rows[0]
                    pdf = next((doc.get('Url') for doc in row.get('DocumentList', []) if doc.get('DocumentType') == 'CONVPDF' and doc.get('Url')), None)
                    if not pdf:
                        raise ValueError('issuer_original_missing')
                    selected.append({'url': self._url(pdf, profile), 'kind': kind, 'published_at': _date(row['FilingDate'])})
            return selected
        soup = BeautifulSoup(html, 'html.parser')
        selected = []
        for form, kind in (('10K', 'annual'), ('10Q', 'interim')):
            rows = []
            for node in soup.find_all('li', link=True):
                label = str(node.get('arialabel', ''))
                year = re.search(r'FY(\d{2})', label)
                if year and form in label.replace('-', '').upper():
                    quarter = next((index for index, word in enumerate(('First', 'Second', 'Third', 'Fourth'), 1) if word.lower() in label.lower()), 4)
                    rows.append((int(year[1]), quarter, node['link']))
            if rows:
                selected.append({'url': self._url(max(rows)[2], profile), 'kind': kind, 'published_at': None})
        return selected

    def _document(self, item: dict[str, Any], profile: dict[str, Any], root: Path) -> dict[str, Any]:
        url, raw = self._fetch(item['url'], profile)
        extension = '.pdf' if raw.startswith(b'%PDF') else '.docx' if raw.startswith(b'PK') and urlsplit(url).path.lower().endswith('.docx') else ''
        if not extension:
            raise ValueError('issuer_original_type_invalid')
        identifier = _id(item['url'])
        original = root/(identifier + extension)
        with tempfile.NamedTemporaryFile(dir=root, suffix=extension, delete=False) as output:
            temporary = Path(output.name)
            output.write(raw)
        try:
            text = extract_official_text(temporary)
            cover = re.sub(r'\s+', ' ', text[:15000])
            normalized = re.sub(r'\s+', '', cover).casefold()
            if not any(re.sub(r'\s+', '', name).casefold() in normalized for name in profile['aliases']):
                raise ValueError('issuer_company_mismatch')
            ein = profile['issuer_tax_id'].split('-')
            if not re.search(ein[0] + r'\s*[-–‑]?\s*' + ein[1], cover):
                raise ValueError('issuer_identity_missing')
            form = 'K' if item['kind'] == 'annual' else 'Q'
            if not re.search(r'\bFORM\s+10\s*[-–‑]?\s*' + form + r'\b', cover, re.I):
                raise ValueError('issuer_form_mismatch')
            pattern = r'(?:fiscal\s+year|quarterly\s+period)\s+ended\s+([A-Za-z]+\s*\d{1,2},?\s*20\d{2})'
            match = re.search(pattern, cover, re.I)
            if not match:
                raise ValueError('issuer_period_missing')
            period_text = re.sub(r'([A-Za-z])(\d)', r'\1 \2', match[1])
            period_text = re.sub(r',\s*', ', ', period_text)
            if ',' not in period_text:period_text = re.sub(r'(\d)\s+(20\d{2})', r'\1, \2', period_text)
            period = _date(period_text)
            today = datetime.now(_KST).date().isoformat()
            published = item.get('published_at')
            date_basis = None
            if not published:
                # Never backdate access to an issuer copy whose precise publication date is unknown.
                index = root/'first-seen.json'
                first_seen = json.loads(index.read_text()) if index.exists() and index.stat().st_size <= 1000000 else {}
                if not isinstance(first_seen, dict) or len(first_seen) > 1000:
                    raise ValueError('invalid_first_seen_index')
                digest = hashlib.sha256(raw).hexdigest()
                published = first_seen.get(digest, today)
                if not isinstance(published, str) or not period <= _date(published) <= today:
                    raise ValueError('invalid_first_seen_date')
                first_seen[digest] = published
                index.with_suffix('.tmp').write_text(json.dumps(first_seen), encoding='utf-8')
                index.with_suffix('.tmp').replace(index)
                date_basis = 'first_retrieved'
            if not period <= published <= today:
                raise ValueError('issuer_filing_date_invalid')
            temporary.replace(original)
            text_path = root/(identifier+'.txt')
            text_path.write_text(text, encoding='utf-8', newline='\n')
            result = {'document_id': identifier, 'company_name': profile['company_name'], 'ticker': profile['ticker'],
                      'document_type': item['kind'], 'provider': 'official_ir', 'filing_origin': 'issuer_filing',
                      'issuer_id': profile['sec_cik'], 'identity_verified': True, 'source_type': 'regulatory_filing',
                      'source_url': url, 'listing_url': profile['filing_index'], 'published_at': published,
                      'report_date': period, 'original_path': str(original), 'text_path': str(text_path),
                      'original_hash': hashlib.sha256(raw).hexdigest(), 'content_hash': hashlib.sha256(text.encode()).hexdigest(), 'content': text}
            if date_basis:result['date_basis'] = date_basis
            return result
        finally:
            temporary.unlink(missing_ok=True)

    def collect(self, company: str, ticker: str) -> dict[str, Any]:
        profile = get_profile(company, ticker)
        if profile['market'] != 'us':
            raise ValueError('issuer_fallback_not_supported')
        root = (self.base_dir/profile['ticker']/'issuer-filings').resolve()
        if not root.is_relative_to(self.base_dir):
            raise ValueError('issuer_cache_outside_company')
        root.mkdir(parents=True, exist_ok=True)
        documents, failures, items = [], [], []
        try:
            items = self._list(profile)
            for item in items:
                try:
                    documents.append(self._document(item, profile, root))
                except (requests.RequestException, OSError, ValueError, KeyError, TypeError, BadZipFile, ParseError, PyPdfError):
                    failures.append({'stage': 'issuer_filings', 'code': 'body_unavailable'})
        except (requests.RequestException, OSError, ValueError, KeyError, TypeError, AttributeError):
            failures.append({'stage': 'issuer_filings', 'code': 'source_unavailable'})
        requested = [_id(item['url']) for item in items]
        required = list(requested)
        annual = next((doc for doc in documents if doc['document_type'] == 'annual'), None)
        interim = next((doc for doc in documents if doc['document_type'] == 'interim'), None)
        if annual and interim and interim['report_date'] <= annual['report_date']:
            required = [annual['document_id']]
        ready = bool(annual) and bool(required) and set(required).issubset(doc['document_id'] for doc in documents)
        return {'documents': documents, 'requested_ids': requested, 'latest_required_ids': required,
                'primary_provider': 'official_ir', 'latest_primary_failed': not ready, 'failures': failures}
