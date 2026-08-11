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
