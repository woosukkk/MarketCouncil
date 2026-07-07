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


def calculate_growth(current, previous):
    if current is None or previous in (None, 0):
        return None

    return ((current - previous) / previous) * 100


def format_percent(value) -> str:
    if value is None:
        return "데이터 없음"

    return f"{value:.1f}%"


def get_financial_data(company_name: str) -> dict:
    ticker_symbol = TICKER_MAP.get(company_name)

    if not ticker_symbol:
        raise ValueError("등록되지 않은 기업입니다.")

    company = yf.Ticker(ticker_symbol)

    history = company.history(period="5d")
    financials = company.financials

    current_price = None
    current_revenue = None
    previous_revenue = None
    current_operating_income = None
    previous_operating_income = None

    if not history.empty:
        current_price = history["Close"].iloc[-1]

    if not financials.empty and len(financials.columns) >= 2:
        current_column = financials.columns[0]
        previous_column = financials.columns[1]

        if "Total Revenue" in financials.index:
            current_revenue = financials.loc[
                "Total Revenue", current_column
            ]
            previous_revenue = financials.loc[
                "Total Revenue", previous_column
            ]

        if "Operating Income" in financials.index:
            current_operating_income = financials.loc[
                "Operating Income", current_column
            ]
            previous_operating_income = financials.loc[
                "Operating Income", previous_column
            ]

    revenue_growth = calculate_growth(
        current_revenue,
        previous_revenue,
    )

    operating_income_growth = calculate_growth(
        current_operating_income,
        previous_operating_income,
    )

    return {
        "ticker": ticker_symbol,
        "current_price": format_number(current_price),
        "current_revenue": format_number(current_revenue),
        "previous_revenue": format_number(previous_revenue),
        "revenue_growth": format_percent(revenue_growth),
        "current_operating_income": format_number(
            current_operating_income
        ),
        "previous_operating_income": format_number(
            previous_operating_income
        ),
        "operating_income_growth": format_percent(
            operating_income_growth
        ),
    }