"""Resolve listed companies without guessing a ticker from a name."""
import re
from functools import lru_cache

import requests
import yfinance as yf
from bs4 import BeautifulSoup


# Presets for the local CLI/viewer; Desktop can select other live search candidates.
TICKER_MAP = {
    "삼성전자": "005930.KS",
    "SK하이닉스": "000660.KS",
    "현대자동차": "005380.KS",
    "현대차": "005380.KS",
    "NAVER": "035420.KS",
    "Apple": "AAPL",
    "Microsoft": "MSFT",
}


def normalize_name(name: str) -> str:
    return re.sub(r"\s+", "", name).casefold()


@lru_cache(maxsize=1)
def korean_listings() -> tuple[dict[str, str], ...]:
    rows = []
    for market, suffix, label in (("stockMkt", ".KS", "KOSPI"), ("kosdaqMkt", ".KQ", "KOSDAQ")):
        response = requests.get(
            "https://kind.krx.co.kr/corpgeneral/corpList.do",
            params={"method": "download", "searchType": "13", "marketType": market},
            timeout=20,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.content.decode("euc-kr"), "html.parser")
        market_rows = []
        for row in soup.select("tr"):
            cells = [cell.get_text(strip=True) for cell in row.find_all("td")]
            if len(cells) >= 3 and re.fullmatch(r"\d{6}", cells[2]):
                market_rows.append({"name": cells[0], "ticker": cells[2] + suffix, "exchange": label})
        if not market_rows:
            raise ValueError("한국거래소 상장 목록을 읽지 못했습니다. 잠시 후 다시 시도하세요.")
        rows.extend(market_rows)
    return tuple(rows)


def find_companies(name: str) -> list[dict[str, str]]:
    name = name.strip()
    if not name or len(name) > 120:
        raise ValueError("기업명을 입력하세요.")
    try:
        known_ticker = preset_ticker(name)
        if re.search(r"[가-힣]", name) or (known_ticker and known_ticker.endswith((".KS", ".KQ"))):
            listings = korean_listings()
            if known_ticker:
                # A known alias must not fall through to a different company's partial match.
                return [row for row in listings if row["ticker"] == known_ticker]
            query = normalize_name(name)
            matches = [row for row in listings if query in normalize_name(row["name"])]
            exact = [row for row in matches if query == normalize_name(row["name"])]
            return exact or matches
        quotes = yf.Search(name, max_results=20, news_count=0, timeout=20).quotes
        matches = {}
        for row in quotes:
            symbol = str(row.get("symbol", ""))
            if row.get("quoteType") == "EQUITY" and re.fullmatch(r"[A-Z0-9][A-Z0-9.^=-]{0,29}", symbol):
                matches[symbol] = {"name": row.get("longname") or row.get("shortname") or symbol,
                                   "ticker": symbol, "exchange": row.get("exchDisp") or row.get("exchange", "")}
        return list(matches.values())
    except ValueError:
        raise
    except Exception as error:
        raise ValueError("기업 검색에 실패했습니다. 인터넷 연결을 확인하고 다시 시도하세요.") from error


def preset_ticker(name: str) -> str | None:
    aliases = {"appleinc.": "AAPL", "microsoftcorporation": "MSFT"}
    query = normalize_name(name)
    return next((ticker for company, ticker in TICKER_MAP.items()
                 if normalize_name(company) == query), aliases.get(query))


def resolve_ticker(name: str, selected_ticker: str | None = None) -> str:
    """Resolve one listing, preserving an explicit Desktop candidate selection."""
    if not name.strip() or len(name.strip()) > 120:
        raise ValueError("기업명을 입력하세요.")
    ticker = selected_ticker or preset_ticker(name)
    if not ticker:
        candidates = find_companies(name)
        exact = [row for row in candidates if normalize_name(row["name"]) == normalize_name(name)]
        matches = exact or candidates
        if len(matches) != 1:
            raise ValueError("종목을 하나로 확인하지 못했습니다. PC 프로그램의 기업 찾기에서 후보를 선택하세요.")
        ticker = matches[0]["ticker"]
    if not isinstance(ticker, str) or not re.fullmatch(r"[A-Z0-9][A-Z0-9.^=-]{0,29}", ticker):
        raise ValueError("올바른 종목코드를 입력하세요.")
    return ticker
