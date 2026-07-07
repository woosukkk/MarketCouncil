import yfinance as yf


TICKER_MAP = {
    "삼성전자": "005930.KS",
    "SK하이닉스": "000660.KS",
    "현대자동차": "005380.KS",
    "애플": "AAPL",
    "엔비디아": "NVDA",
    "테슬라": "TSLA",
}


def format_number(value) -> str:
    if value is None:
        return "데이터 없음"

    return f"{value:,.0f}"


def get_financial_data(company_name: str) -> dict:
    ticker_symbol = TICKER_MAP.get(company_name)

    if not ticker_symbol:
        raise ValueError("등록되지 않은 기업입니다.")

    company = yf.Ticker(ticker_symbol)

    history = company.history(period="5d")
    financials = company.financials

    current_price = None
    revenue = None
    operating_income = None

    if not history.empty:
        current_price = history["Close"].iloc[-1]

    if not financials.empty:
        latest_column = financials.columns[0]

        if "Total Revenue" in financials.index:
            revenue = financials.loc["Total Revenue", latest_column]

        if "Operating Income" in financials.index:
            operating_income = financials.loc[
                "Operating Income",
                latest_column,
            ]

    return {
        "ticker": ticker_symbol,
        "current_price": format_number(current_price),
        "revenue": format_number(revenue),
        "operating_income": format_number(operating_income),
    }