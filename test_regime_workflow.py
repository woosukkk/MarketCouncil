from datetime import date, timedelta

from app.regime_workflow import RegimeWorkflow
from tools.market_regime import detect_regimes


class FakeReasonAgent:
    def analyze(self, payload: dict) -> dict:
        bull_source = payload["evidence_by_regime"]["past_bull"][0]
        bear_source = payload["evidence_by_regime"]["recent_bear"][0]
        return {
            "past_bull": [
                {
                    "claim": "상승 기간에 수주가 증가했다.",
                    "classification": "MARKET_INTERPRETATION",
                    "explanation": "상승 기간 안에 발표됐다.",
                    "evidence": [
                        {
                            "source_id": bull_source["source_id"],
                            "quote_id": bull_source["quotes"][0]["quote_id"],
                            "reason": "수주 증가를 확인한다.",
                        }
                    ],
                }
            ],
            "recent_bear": [
                {
                    "claim": "하락 기간에 전망이 낮아졌다.",
                    "classification": "ANALYST_HYPOTHESIS",
                    "explanation": "하락 기간 안에 발표됐다.",
                    "evidence": [
                        {
                            "source_id": bear_source["source_id"],
                            "quote_id": bear_source["quotes"][0]["quote_id"],
                            "reason": "전망 하향을 확인한다.",
                        }
                    ],
                }
            ],
        }


def test_regime_workflow_limits_evidence_to_each_period_and_resolves_quotes() -> None:
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
    base = RegimeWorkflow(
        reason_agent=FakeReasonAgent(),
        history_provider=lambda ticker: prices,
    )
    detected = detect_regimes("테스트", "TEST", prices)
    bull_date = detected["regimes"]["past_bull"]["start_date"]
    bear_date = detected["regimes"]["recent_bear"]["start_date"]
    catalog = [
        {
            "source_id": "RAG-001",
            "published_at": bull_date,
            "title": "상승 자료",
            "content": "첫 문장. 수주가 증가했습니다. 다음 문장.",
            "quotes": [{"quote_id": "RAG-001-Q01", "text": "수주가 증가했습니다."}],
            "source_url": "https://example.com/bull",
        },
        {
            "source_id": "WEB-001",
            "published_at": bear_date,
            "title": "하락 자료",
            "content": "첫 문장. 전망을 낮췄습니다. 다음 문장.",
            "quotes": [{"quote_id": "WEB-001-Q01", "text": "전망을 낮췄습니다."}],
            "source_url": "https://example.com/bear",
        },
    ]

    result = base.run("테스트", "TEST", catalog)

    bull_reason = result["reasons"]["past_bull"][0]
    bear_reason = result["reasons"]["recent_bear"][0]
    assert bull_reason["verified"] is True
    assert bear_reason["verified"] is True
    assert bull_reason["evidence"][0]["evidence_id"] == "RE-001"
    assert bear_reason["evidence"][0]["evidence_id"] == "RE-002"
    assert bull_reason["evidence"][0]["event_date"] == bull_date


def test_resolve_reasons_rejects_source_from_the_other_regime() -> None:
    raw = {
        "past_bull": [
            {
                "claim": "기간이 잘못된 주장",
                "classification": "ANALYST_HYPOTHESIS",
                "explanation": "",
                "evidence": [
                    {
                        "source_id": "WEB-001",
                        "quote_id": "WEB-001-Q01",
                        "reason": "잘못 연결됨",
                    }
                ],
            }
        ],
        "recent_bear": [],
    }
    catalog = [
        {
            "source_id": "WEB-001",
            "content": "하락 구간 자료",
            "quotes": [{"quote_id": "WEB-001-Q01", "text": "하락 구간 자료"}],
        }
    ]

    reasons = RegimeWorkflow._resolve_reasons(
        raw,
        catalog,
        [],
        [],
        {"past_bull": {"RAG-001"}, "recent_bear": {"WEB-001"}},
    )

    assert reasons["past_bull"][0]["verified"] is False
