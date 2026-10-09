"""Resolve listed companies without guessing a ticker from a name."""
import re
from functools import lru_cache

import requests
import yfinance as yf
from bs4 import BeautifulSoup


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
        if re.search(r"[가-힣]", name):
            query = normalize_name(name)
            matches = [row for row in korean_listings() if query in normalize_name(row["name"])]
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
