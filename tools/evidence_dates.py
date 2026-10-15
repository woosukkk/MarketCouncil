"""Parse explicit dates using modern KST (UTC+09:00), without historic DST rules."""
import re
from datetime import date, datetime, timedelta, timezone


_KOREA = timezone(timedelta(hours=9))
_AWARE_DATETIME = re.compile(
    r"\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:[Zz]|[+-]\d{2}(?::?\d{2})?)"
)


def parse_evidence_date(value: object) -> date | None:
    """Read ISO/DART dates or convert a zoned ISO timestamp to modern KST."""
    if isinstance(value, datetime):
        timestamp = value
    elif isinstance(value, date):
        return value
    elif isinstance(value, str):
        text = value.strip()
        try:
            if re.fullmatch(r"\d{8}", text):
                return date.fromisoformat(f"{text[:4]}-{text[4:6]}-{text[6:]}")
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
                return date.fromisoformat(text)
            if not _AWARE_DATETIME.fullmatch(text):
                return None
            timestamp = datetime.fromisoformat(text.replace("Z", "+00:00").replace("z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        return None
    try:
        return timestamp.astimezone(_KOREA).date()
    except (ValueError, OverflowError):
        return None
