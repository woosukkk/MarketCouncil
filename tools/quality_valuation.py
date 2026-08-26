import math
from statistics import fmean, pstdev
from typing import Any


def _numbers(values: list[Any]) -> list[float]:
    numbers: list[float] = []
    for value in values:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            numbers.append(number)
    return numbers


def validate_quality_inputs(facts: dict[str, Any]) -> list[str]:
    history = facts.get("annual_history", [])
    missing: list[str] = []

    if len(history) < 3:
        missing.append("3개년 이상 연간 재무 데이터")
    if len(_numbers([row.get("free_cash_flow") for row in history])) < 3:
        missing.append("3개년 이상 잉여현금흐름")
    if facts.get("market_cap") is None:
        missing.append("시가총액")
    if len(_numbers([row.get("shares_outstanding") for row in history])) < 2:
        missing.append("2개년 이상 발행 주식 수")

    return missing


def calculate_quality_metrics(facts: dict[str, Any]) -> dict[str, Any]:
    history = facts.get("annual_history", [])
    revenues = _numbers([row.get("revenue") for row in history])
    margins = _numbers([row.get("operating_margin") for row in history])
    free_cash_flows = _numbers([
        row.get("free_cash_flow") for row in history
    ])

    growth_rates = [
        revenues[index] / revenues[index + 1] - 1
        for index in range(len(revenues) - 1)
        if revenues[index + 1] != 0
    ]
    cash_conversion = _numbers([
        row.get("free_cash_flow") / row["net_income"]
        for row in history
        if row.get("free_cash_flow") is not None
        and row.get("net_income") not in (None, 0)
    ])

    latest = history[0] if history else {}
    debt_to_equity = None
    if latest.get("total_debt") is not None and latest.get(
        "stockholders_equity"
    ) not in (None, 0):
        debt_to_equity = (
            latest["total_debt"] / latest["stockholders_equity"]
        )

    shares = _numbers([
        row.get("shares_outstanding") for row in history
    ])
    dilution_rate = None
    if len(shares) >= 2 and shares[-1] != 0:
        dilution_rate = shares[0] / shares[-1] - 1

    normalized_fcf = (
        fmean(free_cash_flows[:5])
        if len(free_cash_flows) >= 3
        else None
    )
    market_cap = facts.get("market_cap")
    fcf_yield = (
        normalized_fcf / market_cap
        if normalized_fcf is not None and market_cap not in (None, 0)
        else None
    )

    return {
        "classification": "derived",
        "period_count": len(history),
        "normalized_fcf": normalized_fcf,
        "fcf_yield": fcf_yield,
        "average_cash_conversion": (
            fmean(cash_conversion) if cash_conversion else None
        ),
        "revenue_growth_volatility": (
            pstdev(growth_rates) if len(growth_rates) >= 2 else None
        ),
        "operating_margin_volatility": (
            pstdev(margins) if len(margins) >= 2 else None
        ),
        "positive_fcf_ratio": (
            sum(value > 0 for value in free_cash_flows)
            / len(free_cash_flows)
            if free_cash_flows
            else None
        ),
        "debt_to_equity": debt_to_equity,
        "dilution_rate": dilution_rate,
        "missing_inputs": validate_quality_inputs(facts),
        "assumptions": [
            "정규화 FCF는 사용 가능한 최근 최대 5개 연도의 평균",
            "가치평가 가정은 적용하지 않음",
        ],
    }
