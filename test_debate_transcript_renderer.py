from tools.debate_transcript_renderer import DebateTranscriptRenderer


def test_render_keeps_every_round_and_original_statement() -> None:
    debate = {
        "company_name": "테스트기업",
        "agenda": [
            {
                "issue_id": "growth",
                "title": "성장 지속 여부",
                "question": "성장이 지속되는가?",
            },
            {
                "issue_id": "risk",
                "title": "위험 요인",
                "question": "위험은 통제 가능한가?",
            },
        ],
        "rounds": [
            _round(1, "1라운드 상승 원문", "1라운드 하락 원문"),
            _round(2, "2라운드 상승 원문", "2라운드 하락 원문"),
        ],
        "moderator_summary": {
            "agreements": [],
            "unresolved_issues": ["성장 지속 여부"],
            "required_evidence": ["다음 분기 실적"],
            "summary": "판단은 사용자에게 남긴다.",
        },
        "stop_reason": "최대 라운드 도달",
        "navigation": {
            "overview": "성장 지속 가능성이 핵심 쟁점이다.",
            "reading_order": ["growth"],
            "issues": [
                {
                    "issue_id": "growth",
                    "title": "성장 지속 여부",
                    "status": "CONTESTED",
                    "core_disagreement": "성장률의 지속 가능성",
                    "round_changes": [
                        {
                            "round": 1,
                            "bull_change": "새 성장 근거를 제시했다.",
                            "bear_change": "지속 기간을 문제 삼았다.",
                            "new_evidence_ids": ["E-001"],
                            "concessions": [],
                            "remaining_question": "다음 분기에도 유지되는가?",
                        }
                    ],
                }
            ],
        },
    }

    markdown = DebateTranscriptRenderer().render(debate)

    assert "### 1라운드" in markdown
    assert "### 2라운드" in markdown
    assert "1라운드 상승 원문" in markdown
    assert "1라운드 하락 원문" in markdown
    assert "2라운드 상승 원문" in markdown
    assert "2라운드 하락 원문" in markdown
    assert "최종 등급" not in markdown
    assert "상승 점수" not in markdown
    assert "## 쟁점 지도" in markdown
    assert "[성장 지속 여부](#issue-growth)" in markdown
    assert "**이 라운드의 변화**" in markdown
    assert "연결 논리" in markdown
    assert "조건·한계" in markdown
    growth_start = markdown.index("## 논제 1. 성장 지속 여부")
    risk_start = markdown.index("## 논제 2. 위험 요인")
    growth_section = markdown[growth_start:risk_start]
    assert "1라운드 상승 원문" in growth_section
    assert "2라운드 상승 원문" in growth_section


def _round(number: int, bull_claim: str, bear_claim: str) -> dict:
    def response(claim: str) -> dict:
        return {
            "issues": [
                {
                    "issue_id": "growth",
                    "claim": claim,
                    "target_claim": "상대 주장 원문",
                    "response": "반론 원문",
                    "warrant": "근거와 주장을 잇는 설명",
                    "qualifier": "조건이 유지되는 동안에만 성립",
                    "evidence": ["근거 원문"],
                    "example_or_data": "사례 원문",
                    "concession": "인정 원문",
                    "missing_evidence": "부족한 근거 원문",
                }
            ]
        }

    return {
        "round": number,
        "bull_response": response(bull_claim),
        "bear_response": response(bear_claim),
        "moderator_review": {
            "issue_reviews": [
                {
                    "issue_id": "growth",
                    "status": "CONTESTED",
                    "assessment": "중재 평가 원문",
                    "question_for_bull": "상승 질문 원문",
                    "question_for_bear": "하락 질문 원문",
                }
            ],
            "repeated_claims": [],
            "missing_evidence": [],
            "reason": "추가 토론 필요",
        },
    }
