import math
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import yfinance as yf


WINDOW_DAYS = 60
RECENT_SEARCH_DAYS = 120


def fetch_price_history(ticker: str, period: str = "2y") -> list[dict[str, Any]]:
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
    frame = frame.loc[:, ["date", "close", "volume"]].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
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
            "close": float(row["Close"]),
            "volume": float(row.get("Volume", 0) or 0),
        }
        for index, row in history.dropna(subset=["Close"]).iterrows()
    ]


def _serializable_prices(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {"date": row.date, "close": float(row.close), "volume": float(row.volume)}
        for row in frame.itertuples(index=False)
    ]


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
