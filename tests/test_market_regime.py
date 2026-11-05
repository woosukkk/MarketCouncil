from datetime import date, timedelta

from tools.market_regime import detect_regimes


def test_detect_regimes_uses_non_overlapping_bull_and_recent_bear_windows() -> None:
    start = date(2025, 1, 1)
    closes = list(range(100, 220)) + list(range(220, 100, -1))
    prices = [
        {
            "date": str(start + timedelta(days=index)),
            "close": close,
            "volume": 1000 + index,
        }
        for index, close in enumerate(closes)
    ]

    result = detect_regimes(
        "테스트",
        "TEST",
        prices,
        benchmark_prices=prices,
        benchmark_ticker="BENCH",
    )
    bull = result["regimes"]["past_bull"]
    bear = result["regimes"]["recent_bear"]

    assert bull["metrics"]["cumulative_return_pct"] > 0
    assert bear["metrics"]["cumulative_return_pct"] < 0
    assert bull["end_date"] < bear["start_date"]
    assert bull["metrics"]["excess_return_pct"] == 0
    assert len(result["comparison"]) == 6


def test_detect_regimes_reports_insufficient_history() -> None:
    result = detect_regimes(
        "테스트",
        "TEST",
        [{"date": "2026-01-01", "close": 100, "volume": 1000}],
    )

    assert result["regimes"] == {}
    assert result["limitations"]


def test_display_series_uses_daily_monthly_and_quarterly_granularity() -> None:
    start = date(2023, 1, 1)
    closes = list(range(100, 700)) + list(range(700, 500, -1))
    prices = [
        {
            "date": str(start + timedelta(days=index)),
            "open": close - 1,
            "high": close + 2,
            "low": close - 2,
            "close": close,
            "volume": 1000 + index,
        }
        for index, close in enumerate(closes)
    ]

    result = detect_regimes(
        "테스트",
        "TEST",
        prices,
        benchmark_prices=prices,
        benchmark_ticker="BENCH",
    )
    display = result["display_series"]

    assert len(result["price_series"]) == 800
    assert len(display["recent_daily"]) == 60
    assert display["medium_monthly"]
    assert display["historical_quarterly"]
    assert display["recent_daily"][0]["open"] is not None
    assert all(row["excess_return_pct"] == 0 for row in display["medium_monthly"])
