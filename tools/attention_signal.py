"""Selection-only attention signals for the daily official company.

These numbers decide which prepared company is analysed today. They are never
placed in the evidence catalog and must not be cited as evidence.
"""
from datetime import date, datetime, timedelta, timezone
from statistics import pstdev
from typing import Any, Callable, Iterable

KST = timezone(timedelta(hours=9))
CAP = 4.0
MIN_RETURNS = 20
MIN_DATED_NEWS = 5
RECENT_DAYS = 2
WINDOW_DAYS = 7


def price_move(closes: Iterable[tuple[date, float]], as_of: date) -> float | None:
    """Latest daily move divided by the issuer's own recent volatility."""
    series = [value for day, value in sorted(closes) if day <= as_of and isinstance(value, (int, float)) and value > 0]
    returns = [later / earlier - 1 for earlier, later in zip(series, series[1:])]
    if len(returns) <= MIN_RETURNS:
        return None
    spread = pstdev(returns[-61:-1])
    return abs(returns[-1]) / spread if spread > 0 else None


def _kst_day(value: object) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:  # an undated or zone-less time is not guessed
        return None
    return parsed.astimezone(KST).date()


def news_surge(published: Iterable[object], as_of: date) -> float | None:
    """Articles per day in the last two days against the issuer's own earlier-week rate."""
    days = [day for value in published if (day := _kst_day(value)) and 0 <= (as_of - day).days < WINDOW_DAYS]
    if len(days) < MIN_DATED_NEWS:
        return None
    recent = sum(1 for day in days if (as_of - day).days < RECENT_DAYS)
    earlier = len(days) - recent
    baseline = max(earlier / (WINDOW_DAYS - RECENT_DAYS), 1 / (WINDOW_DAYS - RECENT_DAYS))
    return (recent / RECENT_DAYS) / baseline


def combine(price: float | None, news: float | None) -> float | None:
    parts = [min(value, CAP) / CAP for value in (price, news) if isinstance(value, (int, float)) and value >= 0]
    return sum(parts) / len(parts) if parts else None


def _closes(ticker: str) -> list[tuple[date, float]]:
    import yfinance as yf
    frame = yf.Ticker(ticker).history(period="6mo", interval="1d", auto_adjust=True)
    return [(index.date(), float(value)) for index, value in frame["Close"].dropna().items()]


def _news_dates(profile: dict[str, Any], search_url: str) -> list[str]:
    from tools.searxng_search import SearxngSearch
    rows = SearxngSearch(search_url).search(profile["company_name"], limit=50, categories="news", time_range="week")
    return [row.get("published_date", "") for row in rows]


def attention_scores(profiles: Iterable[dict[str, Any]], as_of: date, search_url: str | None = None, *,
                     closes: Callable[[str], list[tuple[date, float]]] = _closes,
                     news_dates: Callable[[dict[str, Any], str], list[str]] = _news_dates) -> dict[str, dict[str, float | None]]:
    """Return per-ticker signals. A failed source leaves that signal empty instead of stopping selection."""
    scores: dict[str, dict[str, float | None]] = {}
    for profile in profiles:
        try:
            price = price_move(closes(profile["ticker"]), as_of)
        except Exception:
            price = None
        try:
            news = news_surge(news_dates(profile, search_url), as_of) if search_url else None
        except Exception:
            news = None
        total = combine(price, news)
        scores[profile["ticker"]] = {
            "price_move": round(price, 3) if price is not None else None,
            "news_surge": round(news, 3) if news is not None else None,
            "score": round(total, 4) if total is not None else None,
        }
    return scores
