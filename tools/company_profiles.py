"""Explicit issuer identities and official IR entry points; no network or keys."""
from copy import deepcopy
import re
from typing import Any


PROFILES = (
    {"company_name": "삼성전자", "ticker": "005930.KS", "market": "kr",
     "aliases": ("삼성전자", "Samsung Electronics", "Samsung Electronics Co., Ltd."),
     "sec_cik": None, "ir_sources": (
         {"url": "https://www.samsung.com/global/ir/financial-information/earnings-release/", "host": "www.samsung.com", "path_prefixes": ("/global/ir/",)},
         {"url": "https://images.samsung.com/is/content/samsung/assets/global/ir/docs/", "host": "images.samsung.com", "path_prefixes": ("/is/content/samsung/assets/global/ir/",)},
         {"url": "https://news.samsung.com/global/category/press-resources/press-release", "host": "news.samsung.com", "path_prefixes": ("/global/",)},)},
    {"company_name": "SK하이닉스", "ticker": "000660.KS", "market": "kr",
     "aliases": ("SK하이닉스", "SK hynix", "SK hynix Inc."),
     "sec_cik": None, "ir_sources": (
         {"url": "https://www.skhynix.com/ir/UI-FR-IR12_T3/", "host": "www.skhynix.com", "path_prefixes": ("/ir/",)},
         {"url": "https://news.skhynix.com/en/category/ir/", "host": "news.skhynix.com", "path_prefixes": ("/en/",)},)},
    {"company_name": "현대자동차", "ticker": "005380.KS", "market": "kr",
     "aliases": ("현대자동차", "현대차", "Hyundai Motor", "Hyundai Motor Company"),
     "sec_cik": None, "ir_sources": (
         {"url": "https://www.hyundai.com/worldwide/en/company/ir/financial-information/quarterly-earnings", "host": "www.hyundai.com", "path_prefixes": ("/worldwide/en/company/ir/", "/content/dam/hyundai/ww/en/images/company/investor-relations/")},
         {"url": "https://www.hyundai.com/worldwide/en/newsroom/detail/0000001298", "host": "www.hyundai.com", "path_prefixes": ("/worldwide/en/newsroom/",), "is_document": True},)},
    {"company_name": "NAVER", "ticker": "035420.KS", "market": "kr",
     "aliases": ("NAVER", "NAVER Corporation", "네이버"),
     "sec_cik": None, "ir_sources": (
         {"url": "https://www.navercorp.com/en/investment/earnings", "host": "www.navercorp.com", "path_prefixes": ("/en/investment/", "/investment/", "/api/article/download/")},
         {"url": "https://navercorp.com/en/investment/earnings", "host": "navercorp.com", "path_prefixes": ("/en/investment/", "/investment/", "/api/article/download/")},)},
    {"company_name": "Apple Inc.", "ticker": "AAPL", "market": "us",
     "aliases": ("Apple", "Apple Inc.", "애플"),
     "sec_cik": "0000320193", "ir_sources": (
         {"url": "https://investor.apple.com/investor-relations/default.aspx", "host": "investor.apple.com", "path_prefixes": ("/investor-relations/",)},
         {"url": "https://www.apple.com/newsroom/", "host": "www.apple.com", "path_prefixes": ("/newsroom/",)},
         {"url": "https://images.apple.com/newsroom/", "host": "images.apple.com", "path_prefixes": ("/newsroom/",)},
         {"url": "https://www.apple.com/newsroom/2026/11/apple-reports-fourth-quarter-results/", "host": "www.apple.com", "path_prefixes": ("/newsroom/",), "is_document": True},)},
    {"company_name": "Microsoft Corporation", "ticker": "MSFT", "market": "us",
     "aliases": ("Microsoft", "Microsoft Corporation", "마이크로소프트"),
     "sec_cik": "0000789019", "ir_sources": (
         {"url": "https://www.microsoft.com/en-us/investor/", "host": "www.microsoft.com", "path_prefixes": ("/en-us/investor/", "/investor/")},)},
)

for _profile in PROFILES:
    _profile["issuer_id"] = _profile["sec_cik"]
    _profile["provider"] = "open_dart" if _profile["market"] == "kr" else "sec_edgar"
    _profile["official_ir_hosts"] = tuple(source["host"] for source in _profile["ir_sources"])


def _name(value: str) -> str:
    return re.sub(r"\s+", "", value).casefold()


def get_profile(company: str, ticker: str) -> dict[str, Any]:
    """Require a known company/selected-listing pair; never infer an issuer."""
    if not isinstance(company, str) or not isinstance(ticker, str):
        raise ValueError("기업명과 종목코드를 확인하세요.")
    for profile in PROFILES:
        if ticker.strip().upper() == profile["ticker"]:
            if _name(company) in {_name(alias) for alias in profile["aliases"]}:
                return deepcopy(profile)
            break
    raise ValueError("검증 대상 기업명과 종목코드가 일치하지 않습니다.")
