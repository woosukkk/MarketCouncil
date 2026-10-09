import yfinance as yf
import math
import os
import re
from datetime import datetime

import pandas as pd


TICKER_MAP = {
    "삼성전자": "005930.KS",
    "SK하이닉스": "000660.KS",
    "현대자동차": "005380.KS"
}


def format_number(value) -> str:
    if value is None:
        return "데이터 없음"

    try:
        number = float(value)
    except (TypeError, ValueError):
        return "데이터 없음"

    if not math.isfinite(number):
        return "데이터 없음"

    return f"{number:,.0f}"


def calculate_growth(current, previous):
    if current is None or previous in (None, 0):
        return None

    return ((current - previous) / previous) * 100


def calculate_margin(operating_income, revenue):
    if operating_income is None or revenue in (None, 0):
        return None

    return (operating_income / revenue) * 100


def format_percent(value) -> str:
    if value is None:
        return "데이터 없음"

    return f"{value:.1f}%"


def _number(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _statement_value(
    statement: pd.DataFrame,
    names: tuple[str, ...],
    column: object,
) -> float | None:
    if statement.empty or column not in statement.columns:
        return None
    for name in names:
        if name in statement.index:
            return _number(statement.loc[name, column])
    return None


def _get_market_cap(company: yf.Ticker) -> float | None:
    try:
        return _number(company.fast_info["market_cap"])
    except Exception as error:
        print(f"[시가총액 조회 실패] {error}")
        return None


def _build_annual_history(
    financials: pd.DataFrame,
    cash_flow: pd.DataFrame,
    balance_sheet: pd.DataFrame,
) -> list[dict]:
    history: list[dict] = []
    if financials.empty:
        return history

    for column in financials.columns[:5]:
        revenue = _statement_value(
            financials,
            ("Total Revenue",),
            column,
        )
        operating_income = _statement_value(
            financials,
            ("Operating Income",),
            column,
        )
        operating_margin = (
            operating_income / revenue
            if operating_income is not None and revenue not in (None, 0)
            else None
        )
        history.append({
            "period": str(column)[:10],
            "revenue": revenue,
            "operating_income": operating_income,
            "operating_margin": operating_margin,
            "net_income": _statement_value(
                financials,
                ("Net Income", "Net Income Common Stockholders"),
                column,
            ),
            "operating_cash_flow": _statement_value(
                cash_flow,
                ("Operating Cash Flow", "Total Cash From Operating Activities"),
                column,
            ),
            "capital_expenditure": _statement_value(
                cash_flow,
                ("Capital Expenditure", "Capital Expenditures"),
                column,
            ),
            "free_cash_flow": _statement_value(
                cash_flow,
                ("Free Cash Flow",),
                column,
            ),
            "total_debt": _statement_value(
                balance_sheet,
                ("Total Debt",),
                column,
            ),
            "stockholders_equity": _statement_value(
                balance_sheet,
                ("Stockholders Equity", "Total Stockholder Equity"),
                column,
            ),
            "shares_outstanding": _statement_value(
                balance_sheet,
                ("Ordinary Shares Number", "Share Issued"),
                column,
            ),
        })

    return history
    
def get_latest_price(
    ticker: yf.Ticker,
) -> tuple[float | None, str | None]:
    """
    최근 거래일의 종가와 날짜를 반환한다.

    반환 예시:
    (82400.0, "2026-07-14")

    가격을 조회하지 못하면:
    (None, None)
    """

    try:
        history = ticker.history(
            period="10d",
            interval="1d",
            auto_adjust=False,
        )

        if not history.empty and "Close" in history.columns:
            valid_close = history["Close"].dropna()

            if not valid_close.empty:
                latest_price = float(valid_close.iloc[-1])
                latest_date = valid_close.index[-1]

                if isinstance(latest_date, pd.Timestamp):
                    latest_date_text = latest_date.strftime("%Y-%m-%d")
                else:
                    latest_date_text = str(latest_date)[:10]

                if math.isfinite(latest_price):
                    return latest_price, latest_date_text

    except Exception as error:
        print(f"[주가 history 조회 실패] {error}")

    try:
        latest_price = float(ticker.fast_info["last_price"])

        if math.isfinite(latest_price):
            return latest_price, datetime.now().strftime("%Y-%m-%d")

    except Exception as error:
        print(f"[주가 fast_info 조회 실패] {error}")

    return None, None

def get_financial_data(company_name: str) -> dict:
    ticker_symbol = os.getenv("MARKETCOUNCIL_TICKER") or TICKER_MAP.get(company_name)
    if ticker_symbol and not re.fullmatch(r"[A-Z0-9][A-Z0-9.^=-]{0,29}", ticker_symbol):
        raise ValueError("올바른 종목코드를 입력하세요.")

    if not ticker_symbol:
        raise ValueError("등록되지 않은 기업입니다.")

    company = yf.Ticker(ticker_symbol)
    current_price, price_date = get_latest_price(company)


    try:
        financials = company.financials
        cash_flow = company.cashflow
        balance_sheet = company.balance_sheet
    except Exception as error:
        raise RuntimeError(
            f"{company_name} 재무제표 조회에 실패했습니다: {error}"
        ) from error

    annual_history = _build_annual_history(
        financials,
        cash_flow,
        balance_sheet,
    )
    market_cap = _get_market_cap(company)

    current_revenue = None
    previous_revenue = None
    current_operating_income = None
    previous_operating_income = None

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

    current_operating_margin = calculate_margin(
        current_operating_income,
        current_revenue,
    )

    previous_operating_margin = calculate_margin(
        previous_operating_income,
        previous_revenue,
    )

    financial_facts = {
        "classification": "verified_fact",
        "ticker": ticker_symbol,
        "current_price": current_price,
        "price_date": price_date,
        "market_cap": market_cap,
        "annual_history": annual_history,
    }

    return {
        "ticker": ticker_symbol,
        "current_price": format_number(current_price),
        "price_date": price_date or "데이터 없음",

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

        "current_operating_margin": format_percent(
            current_operating_margin
        ),
        "previous_operating_margin": format_percent(
            previous_operating_margin
        ),
        "financial_facts": financial_facts,
    }
if __name__ == "__main__":
    print("[테스트 시작]")

    result = get_financial_data("삼성전자")

    print("[조회 완료]")

    for key, value in result.items():
        print(f"{key}: {value}")
