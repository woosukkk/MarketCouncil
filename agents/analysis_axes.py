from typing import Any, TypedDict


class AnalysisAxis(TypedDict):
    id: str
    label: str
    negative_label: str
    positive_label: str
    weight: float
    scope: str


BASE_ANALYSIS_AXES: tuple[AnalysisAxis, ...] = (
    {
        "id": "economic_outlook",
        "label": "경기 기대",
        "negative_label": "위축",
        "positive_label": "확장",
        "weight": 0.10,
        "scope": "macro",
    },
    {
        "id": "interest_rate_outlook",
        "label": "금리 기대",
        "negative_label": "긴축",
        "positive_label": "완화",
        "weight": 0.10,
        "scope": "macro",
    },
    {
        "id": "consumption_sentiment",
        "label": "소비·수요 심리",
        "negative_label": "수요 위축",
        "positive_label": "수요 확장",
        "weight": 0.10,
        "scope": "market",
    },
    {
        "id": "risk_appetite",
        "label": "위험 선호",
        "negative_label": "위험 회피",
        "positive_label": "위험 선호",
        "weight": 0.10,
        "scope": "market",
    },
    {
        "id": "earnings_outlook",
        "label": "실적 기대",
        "negative_label": "실적 악화",
        "positive_label": "실적 개선",
        "weight": 0.25,
        "scope": "company",
    },
    {
        "id": "valuation_attractiveness",
        "label": "밸류에이션 매력",
        "negative_label": "고평가 부담",
        "positive_label": "저평가 매력",
        "weight": 0.15,
        "scope": "company",
    },
    {
        "id": "growth_drivers",
        "label": "성장 동력",
        "negative_label": "약화",
        "positive_label": "강화",
        "weight": 0.20,
        "scope": "company",
    },
)

SEMICONDUCTOR_ANALYSIS_AXES: tuple[AnalysisAxis, ...] = (
    {
        "id": "industry_cycle",
        "label": "산업 사이클",
        "negative_label": "하강",
        "positive_label": "상승",
        "weight": 0.12,
        "scope": "industry",
    },
    {
        "id": "supply_chain",
        "label": "공급망",
        "negative_label": "불안",
        "positive_label": "안정",
        "weight": 0.08,
        "scope": "industry",
    },
    {
        "id": "policy_environment",
        "label": "정책 환경",
        "negative_label": "규제 부담",
        "positive_label": "정책 지원",
        "weight": 0.05,
        "scope": "industry",
    },
)

SEMICONDUCTOR_COMPANIES = {
    "삼성전자",
    "SK하이닉스",
    "sk하이닉스",
    "Samsung Electronics",
    "SK Hynix",
}
SEMICONDUCTOR_TICKERS = {"005930.KS", "000660.KS"}


def select_analysis_axes(
    company_name: str,
    financial_data: dict[str, Any] | None = None,
) -> list[AnalysisAxis]:
    axes = [dict(axis) for axis in BASE_ANALYSIS_AXES]
    ticker = str((financial_data or {}).get("ticker", ""))
    if company_name in SEMICONDUCTOR_COMPANIES or ticker in SEMICONDUCTOR_TICKERS:
        axes.extend(dict(axis) for axis in SEMICONDUCTOR_ANALYSIS_AXES)
    return _normalize_weights(axes)


def axes_by_id(axes: list[AnalysisAxis]) -> dict[str, AnalysisAxis]:
    return {axis["id"]: axis for axis in axes}


def _normalize_weights(axes: list[AnalysisAxis]) -> list[AnalysisAxis]:
    total = sum(float(axis["weight"]) for axis in axes)
    if total <= 0:
        return axes
    return [
        {**axis, "weight": round(float(axis["weight"]) / total, 6)}
        for axis in axes
    ]
