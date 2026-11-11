"""Selection-only attention signals for the daily official company.

These numbers decide which prepared company is analysed today. They are never
placed in the evidence catalog and must not be cited as evidence.
"""
from datetime import date, datetime, timedelta
from statistics import pstdev
from typing import Any, Callable, Iterable

CAP = 4.0
MIN_RETURNS = 20
MIN_ARTICLES = 10
WINDOW = timedelta(hours=24)
NEWS_URL = "https://naverapihub.apigw.ntruss.com/search/v1/news"
NEWS_PAGES = 10
NEWS_NAMES = {"005930.KS": "삼성전자", "000660.KS": "SK하이닉스", "005380.KS": "현대차",
              "035420.KS": "네이버", "AAPL": "애플", "MSFT": "마이크로소프트"}


def price_move(closes: Iterable[tuple[date, float]], as_of: date) -> float | None:
    """Latest daily move divided by the issuer's own recent volatility."""
    series = [value for day, value in sorted(closes) if day <= as_of and isinstance(value, (int, float)) and value > 0]
    returns = [later / earlier - 1 for earlier, later in zip(series, series[1:])]
    if len(returns) <= MIN_RETURNS:
        return None
    spread = pstdev(returns[-61:-1])
    return abs(returns[-1]) / spread if spread > 0 else None


def news_surge(published: Iterable[datetime], now: datetime, complete: bool) -> float | None:
    """Articles in the last 24 hours against the issuer's own previous 24 hours.

    `complete` means the list reaches back at least 48 hours or holds every match.
    """
    if not complete:
        return None
    recent = previous = 0
    for moment in published:
        if not isinstance(moment, datetime) or moment.tzinfo is None:  # a zone-less time is not guessed
            continue
        age = now - moment
        if timedelta(0) <= age < WINDOW:
            recent += 1
        elif WINDOW <= age < 2 * WINDOW:
            previous += 1
    if recent + previous < MIN_ARTICLES:
        return None
    return recent / max(previous, 1)


def combine(price: float | None, news: float | None) -> float | None:
    parts = [min(value, CAP) / CAP for value in (price, news) if isinstance(value, (int, float)) and value >= 0]
    return sum(parts) / len(parts) if parts else None


def _closes(ticker: str) -> list[tuple[date, float]]:
    import yfinance as yf
    frame = yf.Ticker(ticker).history(period="6mo", interval="1d", auto_adjust=True)
    return [(index.date(), float(value)) for index, value in frame["Close"].dropna().items()]


def naver_news(client_id: str, client_secret: str, *, get: Callable[..., Any] | None = None,
               clock: Callable[[], datetime] | None = None) -> Callable[[dict[str, Any]], float | None]:
    """Build a news lookup that counts recent stock-related articles for one issuer."""
    from email.utils import parsedate_to_datetime
    from datetime import timezone
    if get is None:
        import requests
        get = requests.get
    clock = clock or (lambda: datetime.now(timezone.utc))
    headers = {"X-NCP-APIGW-API-KEY-ID": client_id, "X-NCP-APIGW-API-KEY": client_secret}

    def lookup(profile: dict[str, Any]) -> float | None:
        now, moments, complete = clock(), [], False
        query = NEWS_NAMES.get(profile["ticker"], profile["company_name"]) + " 주가"
        for page in range(NEWS_PAGES):
            response = get(NEWS_URL, params={"query": query, "display": 100, "start": page * 100 + 1, "sort": "date"},
                           headers=headers, timeout=15)
            if response.status_code != 200:  # includes authentication and quota errors: no retry, no signal
                return None
            items = response.json().get("items") or []
            for item in items:
                try:
                    moments.append(parsedate_to_datetime(item.get("pubDate", "")))
                except (TypeError, ValueError):
                    continue
            if len(items) < 100 or (moments and now - min(moments) >= 2 * WINDOW):
                complete = True
                break
        return news_surge(moments, now, complete)

    return lookup


def attention_scores(profiles: Iterable[dict[str, Any]], as_of: date, *,
                     closes: Callable[[str], list[tuple[date, float]]] = _closes,
                     news: Callable[[dict[str, Any]], float | None] | None = None) -> dict[str, dict[str, float | None]]:
    """Return per-ticker signals. A failed source leaves that signal empty instead of stopping selection."""
    scores: dict[str, dict[str, float | None]] = {}
    for profile in profiles:
        try:
            price = price_move(closes(profile["ticker"]), as_of)
        except Exception:
            price = None
        try:
            volume = news(profile) if news else None
        except Exception:
            volume = None
        total = combine(price, volume)
        scores[profile["ticker"]] = {
            "price_move": round(price, 3) if price is not None else None,
            "news_surge": round(volume, 3) if volume is not None else None,
            "score": round(total, 4) if total is not None else None,
        }
    return scores
