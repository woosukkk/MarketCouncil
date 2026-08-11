from tools.debate_transcript_renderer import DebateTranscriptRenderer


def test_render_keeps_every_round_and_original_statement() -> None:
    debate = {
        "company_name": "테스트기업",
        "agenda": [
            {
                "issue_id": "growth",
                "title": "성장 지속 여부",
                "question": "성장이 지속되는가?",
            }
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
    }

    markdown = DebateTranscriptRenderer().render(debate)

    assert "## 1라운드" in markdown
    assert "## 2라운드" in markdown
    assert "1라운드 상승 원문" in markdown
    assert "1라운드 하락 원문" in markdown
    assert "2라운드 상승 원문" in markdown
    assert "2라운드 하락 원문" in markdown
    assert "최종 등급" not in markdown
    assert "상승 점수" not in markdown


def _round(number: int, bull_claim: str, bear_claim: str) -> dict:
    def response(claim: str) -> dict:
        return {
            "issues": [
                {
                    "issue_id": "growth",
                    "claim": claim,
                    "target_claim": "상대 주장 원문",
                    "response": "반론 원문",
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
