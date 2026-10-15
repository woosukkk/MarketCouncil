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
_SCALES = {"조": "1e12", "억": "1e8", "만": "1e4", "천": "1e3",
           "trillion": "1e12", "billion": "1e9", "million": "1e6", "thousand": "1e3"}
_STOCK_CONTEXT = re.compile(r"주식|발행|유통|취득|소각|증자|지분|거래량|매수|매도|매입|보유|보통주|우선주|shares?", re.IGNORECASE)
_SHORT_TERM = re.compile(
    r"단기|(?:향후|앞으로|다음)\s*(?:[1-4]\s*[~～–-]\s*)?[1-4]\s*주"
    r"|[1-4]\s*[~～–-]\s*[1-4]\s*주|[1-4]\s*주\s*(?:이내|내|후|동안)",
)
_FORECAST = re.compile(r"전망|예상|가이던스|목표주가|예측|forecast|outlook|guidance|projection", re.IGNORECASE)


def _financial_numbers(text: str) -> set[tuple[str, Decimal]]:
    """Read explicit financial units, excluding calendar values and week horizons."""
    numbers = set()
    for match in _NUMBER.finditer(text):
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
    quoted_numbers = set()
    warnings = set()
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
        "numeric_status": "not_applicable" if not claim_numbers else "needs_review" if unmatched else "values_present",
        "claim_number_count": len(claim_numbers),
        "unmatched_number_count": len(unmatched),
        "as_of_date_valid": cutoff is not None,
        "warnings": sorted(warnings),
    }
