"""Selection-only attention signal for the daily official company.

The number decides which prepared company is analysed today. It is never placed
in the evidence catalog and must not be cited as evidence.
"""
from datetime import date
from statistics import pstdev
from typing import Any, Callable, Iterable

CAP = 4.0
MIN_RETURNS = 20


def price_move(closes: Iterable[tuple[date, float]], as_of: date) -> float | None:
    """Latest daily move divided by the issuer's own recent volatility."""
    series = [value for day, value in sorted(closes) if day <= as_of and isinstance(value, (int, float)) and value > 0]
    returns = [later / earlier - 1 for earlier, later in zip(series, series[1:])]
    if len(returns) <= MIN_RETURNS:
        return None
    spread = pstdev(returns[-61:-1])
    return abs(returns[-1]) / spread if spread > 0 else None


def _closes(ticker: str) -> list[tuple[date, float]]:
    import yfinance as yf
    frame = yf.Ticker(ticker).history(period="6mo", interval="1d", auto_adjust=True)
    return [(index.date(), float(value)) for index, value in frame["Close"].dropna().items()]


def attention_scores(profiles: Iterable[dict[str, Any]], as_of: date, *,
                     closes: Callable[[str], list[tuple[date, float]]] = _closes) -> dict[str, dict[str, float | None]]:
    """Return per-ticker signals. A failed lookup leaves that issuer unscored instead of stopping selection."""
    scores: dict[str, dict[str, float | None]] = {}
    for profile in profiles:
        try:
            price = price_move(closes(profile["ticker"]), as_of)
        except Exception:
            price = None
        scores[profile["ticker"]] = {
            "price_move": round(price, 3) if price is not None else None,
            "score": round(min(price, CAP) / CAP, 4) if price is not None else None,
        }
    return scores
