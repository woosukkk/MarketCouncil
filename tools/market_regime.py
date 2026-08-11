import math
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import yfinance as yf


WINDOW_DAYS = 60
RECENT_SEARCH_DAYS = 120


def fetch_price_history(ticker: str, period: str = "3y") -> list[dict[str, Any]]:
    try:
        history = yf.Ticker(ticker).history(
            period=period,
            interval="1d",
            auto_adjust=False,
        )
    except Exception as error:
        raise RuntimeError(f"가격 시계열을 수집하지 못했습니다: {error}") from error
    if history.empty or "Close" not in history.columns:
        raise RuntimeError("가격 시계열이 비어 있습니다.")
    return _records(history)


def detect_regimes(
    company_name: str,
    ticker: str,
    prices: list[dict[str, Any]],
    window_days: int = WINDOW_DAYS,
    recent_search_days: int = RECENT_SEARCH_DAYS,
    benchmark_prices: list[dict[str, Any]] | None = None,
    benchmark_ticker: str = "",
) -> dict[str, Any]:
    frame = _frame(prices)
    minimum = window_days * 2
    if len(frame) < minimum:
        return _unavailable(company_name, ticker, prices, minimum)

    returns = frame["close"].div(frame["close"].shift(window_days - 1)).sub(1)
    recent_start = max(window_days - 1, len(frame) - recent_search_days)
    recent_end = int(returns.iloc[recent_start:].idxmin())
    recent = _window(frame, recent_end - window_days + 1, recent_end, "recent_bear")

    historical_returns = returns.iloc[window_days - 1 : recent["start_index"]]
    if historical_returns.empty:
        return _unavailable(company_name, ticker, prices, minimum)
    bull_end = int(historical_returns.idxmax())
    bull = _window(frame, bull_end - window_days + 1, bull_end, "past_bull")

    benchmark_frame = _frame(benchmark_prices) if benchmark_prices else pd.DataFrame()
    if not benchmark_frame.empty:
        _add_benchmark_metrics(bull, benchmark_frame)
        _add_benchmark_metrics(recent, benchmark_frame)

    limitations: list[str] = []
    if recent["metrics"]["cumulative_return_pct"] >= 0:
        limitations.append("최근 탐색 구간에서 음의 60거래일 수익률을 찾지 못했습니다.")
    if bull["metrics"]["cumulative_return_pct"] <= 0:
        limitations.append("최근 하락 구간 이전에 양의 60거래일 수익률을 찾지 못했습니다.")

    for item in (bull, recent):
        item.pop("start_index", None)
        item.pop("end_index", None)
    return {
        "schema_version": 1,
        "company_name": company_name,
        "ticker": ticker,
        "benchmark_ticker": benchmark_ticker,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "methodology": {
            "window_days": window_days,
            "recent_search_days": recent_search_days,
            "description": (
                "최근 탐색 구간에서 수익률이 가장 낮은 고정 길이 구간과, "
                "그 이전에서 수익률이 가장 높은 비중복 구간을 비교합니다."
            ),
        },
        "price_series": _serializable_prices(frame),
        "benchmark_series": (
            _serializable_prices(benchmark_frame) if not benchmark_frame.empty else []
        ),
        "display_series": _display_series(frame, benchmark_frame),
        "regimes": {"past_bull": bull, "recent_bear": recent},
        "comparison": _comparison(bull, recent),
        "reasons": {"past_bull": [], "recent_bear": []},
        "limitations": limitations,
    }


def _window(
    frame: pd.DataFrame,
    start: int,
    end: int,
    regime_id: str,
) -> dict[str, Any]:
    period = frame.iloc[start : end + 1]
    close = period["close"]
    daily_returns = close.pct_change().dropna()
    drawdown = close.div(close.cummax()).sub(1)
    preceding = frame.iloc[max(0, start - len(period)) : start]
    prior_volume = preceding["volume"].mean() if not preceding.empty else math.nan
    average_volume = period["volume"].mean()
    volume_ratio = average_volume / prior_volume if prior_volume and math.isfinite(prior_volume) else None
    return {
        "regime_id": regime_id,
        "start_index": start,
        "end_index": end,
        "start_date": str(period.iloc[0]["date"]),
        "end_date": str(period.iloc[-1]["date"]),
        "metrics": {
            "start_price": _round(period.iloc[0]["close"], 2),
            "end_price": _round(period.iloc[-1]["close"], 2),
            "cumulative_return_pct": _round((close.iloc[-1] / close.iloc[0] - 1) * 100, 2),
            "max_drawdown_pct": _round(drawdown.min() * 100, 2),
            "annualized_volatility_pct": _round(daily_returns.std() * math.sqrt(252) * 100, 2),
            "average_volume": _round(average_volume, 0),
            "volume_ratio": _round(volume_ratio, 2),
            "trading_days": int(len(period)),
        },
    }


def _comparison(bull: dict[str, Any], bear: dict[str, Any]) -> list[dict[str, Any]]:
    definitions = [
        ("누적수익률", "cumulative_return_pct", "%"),
        ("시장 대비 초과수익률", "excess_return_pct", "%"),
        ("최대 낙폭", "max_drawdown_pct", "%"),
        ("연환산 변동성", "annualized_volatility_pct", "%"),
        ("평균 거래량", "average_volume", "주"),
        ("직전 구간 대비 거래량", "volume_ratio", "배"),
    ]
    rows = []
    for label, key, unit in definitions:
        bull_value = bull["metrics"].get(key)
        bear_value = bear["metrics"].get(key)
        change = (
            _round(float(bear_value) - float(bull_value), 2)
            if bull_value is not None and bear_value is not None
            else None
        )
        rows.append({
            "metric": label,
            "past_bull": bull_value,
            "recent_bear": bear_value,
            "change": change,
            "unit": unit,
        })
    return rows


def _frame(prices: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(prices).rename(columns=str.lower)
    required = {"date", "close", "volume"}
    if not required.issubset(frame.columns):
        raise ValueError(f"가격 데이터에 필수 열이 없습니다: {sorted(required)}")
    for column in ("open", "high", "low"):
        if column not in frame:
            frame[column] = frame["close"]
    frame = frame.loc[:, ["date", "open", "high", "low", "close", "volume"]].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    for column in ("open", "high", "low", "close"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce")
    frame = frame.dropna(subset=["date", "close"]).sort_values("date").drop_duplicates("date")
    frame["volume"] = frame["volume"].fillna(0)
    return frame.reset_index(drop=True)


def _add_benchmark_metrics(
    regime: dict[str, Any],
    benchmark: pd.DataFrame,
) -> None:
    period = benchmark[
        benchmark["date"].between(regime["start_date"], regime["end_date"])
    ]
    if len(period) < 2:
        regime["metrics"]["benchmark_return_pct"] = None
        regime["metrics"]["excess_return_pct"] = None
        return
    benchmark_return = (period.iloc[-1]["close"] / period.iloc[0]["close"] - 1) * 100
    regime["metrics"]["benchmark_return_pct"] = _round(benchmark_return, 2)
    regime["metrics"]["excess_return_pct"] = _round(
        regime["metrics"]["cumulative_return_pct"] - benchmark_return,
        2,
    )


def _records(history: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {
            "date": index.strftime("%Y-%m-%d"),
            "open": float(row.get("Open", row["Close"])),
            "high": float(row.get("High", row["Close"])),
            "low": float(row.get("Low", row["Close"])),
            "close": float(row["Close"]),
            "volume": float(row.get("Volume", 0) or 0),
        }
        for index, row in history.dropna(subset=["Close"]).iterrows()
    ]


def _serializable_prices(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {
            "date": row.date,
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
            "volume": float(row.volume),
        }
        for row in frame.itertuples(index=False)
    ]


def _display_series(
    frame: pd.DataFrame,
    benchmark: pd.DataFrame,
) -> dict[str, list[dict[str, Any]]]:
    recent_start = max(0, len(frame) - 60)
    medium_start = max(0, len(frame) - 252)
    daily_returns = frame["close"].pct_change().mul(100)
    recent_daily = []
    for index in range(recent_start, len(frame)):
        row = frame.iloc[index]
        benchmark_return = _daily_benchmark_return(benchmark, str(row["date"]))
        stock_return = _round(daily_returns.iloc[index], 2)
        recent_daily.append({
            "period": str(row["date"]),
            "start_date": str(row["date"]),
            "end_date": str(row["date"]),
            "open": _round(row["open"], 2),
            "high": _round(row["high"], 2),
            "low": _round(row["low"], 2),
            "close": _round(row["close"], 2),
            "return_pct": stock_return,
            "max_drawdown_pct": None,
            "annualized_volatility_pct": None,
            "average_volume": _round(row["volume"], 0),
            "benchmark_return_pct": benchmark_return,
            "excess_return_pct": (
                _round(stock_return - benchmark_return, 2)
                if stock_return is not None and benchmark_return is not None
                else None
            ),
        })
    return {
        "recent_daily": recent_daily,
        "medium_monthly": _aggregate_periods(
            frame.iloc[medium_start:recent_start],
            benchmark,
            "M",
        ),
        "historical_quarterly": _aggregate_periods(
            frame.iloc[:medium_start],
            benchmark,
            "Q",
        ),
    }


def _aggregate_periods(
    frame: pd.DataFrame,
    benchmark: pd.DataFrame,
    frequency: str,
) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    grouped = frame.copy()
    grouped["period"] = pd.to_datetime(grouped["date"]).dt.to_period(frequency).astype(str)
    rows = []
    for period_name, period in grouped.groupby("period", sort=True):
        close = period["close"]
        returns = close.pct_change().dropna()
        benchmark_return = _benchmark_period_return(
            benchmark,
            str(period.iloc[0]["date"]),
            str(period.iloc[-1]["date"]),
        )
        stock_return = _round((close.iloc[-1] / close.iloc[0] - 1) * 100, 2)
        rows.append({
            "period": period_name.replace("Q", "-Q"),
            "start_date": str(period.iloc[0]["date"]),
            "end_date": str(period.iloc[-1]["date"]),
            "open": _round(period.iloc[0]["open"], 2),
            "high": _round(period["high"].max(), 2),
            "low": _round(period["low"].min(), 2),
            "close": _round(period.iloc[-1]["close"], 2),
            "return_pct": stock_return,
            "max_drawdown_pct": _round(close.div(close.cummax()).sub(1).min() * 100, 2),
            "annualized_volatility_pct": _round(returns.std() * math.sqrt(252) * 100, 2),
            "average_volume": _round(period["volume"].mean(), 0),
            "benchmark_return_pct": benchmark_return,
            "excess_return_pct": (
                _round(stock_return - benchmark_return, 2)
                if stock_return is not None and benchmark_return is not None
                else None
            ),
        })
    return rows


def _benchmark_period_return(
    benchmark: pd.DataFrame,
    start_date: str,
    end_date: str,
) -> float | None:
    if benchmark.empty:
        return None
    period = benchmark[benchmark["date"].between(start_date, end_date)]
    if len(period) < 2:
        return None
    return _round((period.iloc[-1]["close"] / period.iloc[0]["close"] - 1) * 100, 2)


def _daily_benchmark_return(benchmark: pd.DataFrame, target_date: str) -> float | None:
    if benchmark.empty:
        return None
    matches = benchmark.index[benchmark["date"] == target_date].tolist()
    if not matches or matches[0] == 0:
        return None
    index = matches[0]
    return _round((benchmark.iloc[index]["close"] / benchmark.iloc[index - 1]["close"] - 1) * 100, 2)


def _unavailable(
    company_name: str,
    ticker: str,
    prices: list[dict[str, Any]],
    minimum: int,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "company_name": company_name,
        "ticker": ticker,
        "benchmark_ticker": "",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "methodology": {"window_days": WINDOW_DAYS, "recent_search_days": RECENT_SEARCH_DAYS},
        "price_series": prices,
        "benchmark_series": [],
        "display_series": {
            "recent_daily": [],
            "medium_monthly": [],
            "historical_quarterly": [],
        },
        "regimes": {},
        "comparison": [],
        "reasons": {"past_bull": [], "recent_bear": []},
        "limitations": [f"국면 비교에는 최소 {minimum}거래일이 필요합니다."],
    }


def _round(value: Any, digits: int) -> float | None:
    if value is None:
        return None
    number = float(value)
    return round(number, digits) if math.isfinite(number) else None
