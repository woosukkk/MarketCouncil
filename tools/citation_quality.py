"""Conservative citation checks; matching IDs or numbers never proves a claim true."""
import re
from decimal import Decimal
from typing import Any

from tools.evidence_dates import parse_evidence_date
from tools.evidence_text import is_navigation_text


_NUMBER = re.compile(
    r"(?<![\d.])(?P<currency>KRW|USD|[$₩])?\s*"
    r"(?P<number>[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*"
    r"(?P<scale>trillion|billion|million|thousand|조|억|만|천)?\s*"
    r"(?P<unit>퍼센트포인트|퍼센트|%p|%|KRW|USD|달러|원|shares?|주|배)?",
    re.IGNORECASE,
)
_DECIMAL_NUMBER = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
_KRW_COMPOUND = re.compile(r"(?<![\d.,eE+-])(?P<value>[+-]?" + _DECIMAL_NUMBER + r"(?:\s*[조억만천백십]\s*(?:" + _DECIMAL_NUMBER + r")?)+)\s*원")
_TABLE_VALUE = re.compile(r"[+-]?" + _DECIMAL_NUMBER)
_TABLE_LABEL = re.compile(r"(?:보통주식|우선주식|기타주식|보통주|우선주)")
_SCALES = {"조": "1e12", "억": "1e8", "만": "1e4", "천": "1e3",
           "trillion": "1e12", "billion": "1e9", "million": "1e6", "thousand": "1e3"}
_STOCK_CONTEXT = re.compile(r"주식|발행|유통|취득|소각|증자|지분|거래량|매수|매도|매입|보유|보통주|우선주|shares?", re.IGNORECASE)
_SHORT_TERM = re.compile(
    r"단기|(?:향후|앞으로|다음)\s*(?:[1-4]\s*[~～–-]\s*)?[1-4]\s*주"
    r"|[1-4]\s*[~～–-]\s*[1-4]\s*주|[1-4]\s*주\s*(?:이내|내|후|동안)",
)
_FORECAST = re.compile(r"전망|예상|가이던스|목표주가|예측|forecast|outlook|guidance|projection", re.IGNORECASE)


def _compound_krw(expression: str) -> Decimal | None:
    """Add descending Korean money groups; a small unit may qualify a large one."""
    compact = re.sub(r"\s+", "", expression)
    sign = -1 if compact.startswith("-") else 1
    compact = compact.lstrip("+-")
    tokens = re.findall(_DECIMAL_NUMBER + r"|[조억만천백십]", compact)
    if "".join(tokens) != compact:
        return None
    total: Decimal | None = None
    group: Decimal | None = None
    pending: Decimal | None = None
    previous_large, previous_small = Decimal("1e16"), Decimal("1e4")
    for token in tokens:
        if token[0].isdigit():
            if pending is not None:
                return None
            pending = Decimal(token.replace(",", ""))
            continue
        unit = Decimal({"조": "1e12", "억": "1e8", "만": "1e4", "천": "1e3", "백": "1e2", "십": "1e1"}[token])
        if unit >= Decimal("1e4"):
            if unit >= previous_large or (pending is None and group is None):
                return None
            coefficient = pending if group is None else group if pending is None else group + pending
            part = coefficient * unit
            total = part if total is None else total + part
            group, pending = None, None
            previous_large, previous_small = unit, Decimal("1e4")
        else:
            if unit >= previous_small or pending is None:
                return None
            part = pending * unit
            group = part if group is None else group + part
            pending, previous_small = None, unit
    parts = [part for part in (total, group, pending) if part is not None]
    value = parts[0]
    for part in parts[1:]:
        value += part
    return sign * value


def _table_numbers(text: str) -> set[tuple[str, Decimal]]:
    """Read numeric rows only immediately below an explicit currency/share header."""
    numbers = set()
    lines = text.splitlines()
    for index, line in enumerate(lines):
        unit = re.search(r"\(\s*(원|주)\s*\)", line)
        if unit is None or (unit[1] == "주" and not _STOCK_CONTEXT.search(line)):
            continue
        dimension = "KRW" if unit[1] == "원" else "shares"
        for row in lines[index + 1:index + 5]:
            row = row.strip()
            if _TABLE_VALUE.fullmatch(row):
                numbers.add((dimension, Decimal(row.replace(",", ""))))
            elif not row or _TABLE_LABEL.fullmatch(row):
                continue
            else:
                break
    return numbers


def _financial_numbers(text: str) -> set[tuple[str, Decimal]]:
    """Read explicit financial units, excluding calendar values and week horizons."""
    numbers = _table_numbers(text)
    compound_spans = []
    for compound in _KRW_COMPOUND.finditer(text):
        compound_spans.append(compound.span())
        value = _compound_krw(compound["value"])
        if value is not None:
            numbers.add(("KRW", value))
    for match in _NUMBER.finditer(text):
        if any(match.start() < end and start < match.end() for start, end in compound_spans):
            continue
        raw = match["number"]
        value = Decimal(raw.replace(",", ""))
        scale = (match["scale"] or "").lower()
        unit = (match["unit"] or "").lower()
        currency = (match["currency"] or "").lower()
        if not unit and not currency and not scale:
            continue
        if unit == "주":
            if any(start <= match.start() and match.end() <= end for start, end in (horizon.span() for horizon in _SHORT_TERM.finditer(text))):
                continue
            before, after = text[max(0, match.start() - 18):match.start()], text[match.end():match.end() + 8]
            if re.match(r"\s*(?:일|후|뒤|전|동안|이내|간|째|차)", after):
                continue
            if not scale and abs(value) <= 52 and re.search(r"(?:향후|앞으로|다음|지난|최근)\s*(?:\d+\s*[~～–-]\s*)?$", before):
                continue
            context = text[max(0, match.start() - 24):match.end() + 24]
            if not scale and "," not in raw and not _STOCK_CONTEXT.search(context):
                continue
            dimension = "shares"
        elif unit in {"share", "shares"}:
            dimension = "shares"
        elif unit in {"%", "퍼센트"}:
            dimension = "percent"
        elif unit in {"%p", "퍼센트포인트"}:
            dimension = "percentage_points"
        elif unit == "배":
            dimension = "multiple"
        elif unit in {"원", "krw"} or currency in {"₩", "krw"}:
            dimension = "KRW"
        elif unit in {"달러", "usd"} or currency in {"$", "usd"}:
            dimension = "USD"
        else:
            dimension = "scaled_number"
        numbers.add((dimension, value * Decimal(_SCALES.get(scale, "1"))))
    return numbers


def assess_issue_evidence(
    issue: dict[str, Any],
    catalog: list[dict[str, Any]],
    as_of_date: object = None,
) -> dict[str, Any]:
    """Return review warnings without changing inputs or inferring semantic truth.

    Checked fields: claim, response, warrant, example_or_data. Opponent target_claim
    and conditional qualifier/concession are excluded. claim_number_count keeps its
    original name and counts distinct values across the four checked fields.
    Numeric checks compare explicit values and units only. They do not check the
    metric, period, direction, calculation, or whether a quotation supports a claim.
    Missing/invalid as_of_date disables future/staleness comparisons.
    """
    sources = {str(source.get("source_id", "")): source for source in catalog}
    claim_texts = [issue[key] for key in ("claim", "response", "warrant", "example_or_data")
                   if isinstance(issue.get(key), str)]
    claim_numbers = {number for text in claim_texts for number in _financial_numbers(text)}
    short_term = any(_SHORT_TERM.search(text) for text in claim_texts)
    invalid_claim_number = any(_compound_krw(match["value"]) is None for text in claim_texts for match in _KRW_COMPOUND.finditer(text))
    quoted_numbers = set()
    warnings = {"invalid_numeric_format"} if invalid_claim_number else set()
    evidence = issue.get("evidence", [])
    if not isinstance(evidence, list):
        evidence = []
    identity_valid = True
    cutoff = parse_evidence_date(as_of_date)
    for item in evidence:
        if not isinstance(item, dict):
            identity_valid = False
            continue
        source = sources.get(str(item.get("source_id", "")))
        quote = next((quote for quote in (source or {}).get("quotes", [])
                      if str(quote.get("quote_id", "")) == str(item.get("quote_id", ""))), None)
        if source is None or quote is None or not quote.get("text"):
            identity_valid = False
            continue
        text = str(quote["text"])
        if ("exact_quote" in item and item["exact_quote"] != text) or ("content" in source and text not in str(source["content"])):
            identity_valid = False
            continue
        if is_navigation_text(text):
            warnings.add("non_evidentiary_quote")
            continue
        if any(_compound_krw(match["value"]) is None for match in _KRW_COMPOUND.finditer(text)):
            warnings.add("invalid_numeric_format")
        quoted_numbers.update(_financial_numbers(text))
        published = parse_evidence_date(source.get("published_at") or source.get("published_date"))
        if published is None:
            warnings.add("source_date_missing")
        elif cutoff is not None:
            if published > cutoff:
                warnings.add("future_source")
            elif (cutoff - published).days > 90 and short_term and _FORECAST.search(text):
                warnings.add("stale_forecast")
    # Displayed values may be rounded; the tolerance follows the claim's shown unit.
    unmatched = {
        (dimension, value) for dimension, value in claim_numbers
        if not any(
            quote_dimension == dimension
            and (quote_value == value or abs(quote_value - value) < Decimal(1).scaleb(value.as_tuple().exponent) / 2)
            for quote_dimension, quote_value in quoted_numbers
        )
    }
    if unmatched:
        warnings.add("number_not_in_quotes")
    return {
        "identity_status": "missing" if not evidence else "matched" if identity_valid else "invalid",
        "semantic_status": "not_evaluated",
        "numeric_status": "needs_review" if invalid_claim_number or unmatched or "invalid_numeric_format" in warnings else "not_applicable" if not claim_numbers else "values_present",
        "claim_number_count": len(claim_numbers),
        "unmatched_number_count": len(unmatched),
        "as_of_date_valid": cutoff is not None,
        "warnings": sorted(warnings),
    }
