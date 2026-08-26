from app.debate_view_data import collect_evidence, find_issue_turn, round_change


def test_collect_evidence_supports_verified_and_legacy_items() -> None:
    debate = {
        "rounds": [
            {
                "bull_response": {
                    "issues": [
                        {
                            "issue_id": "growth",
                            "evidence": [
                                {"evidence_id": "E-001", "verified": True},
                                "기존 문자열 근거",
                            ],
                        }
                    ]
                },
                "bear_response": {"issues": []},
            }
        ]
    }

    evidence = collect_evidence(debate)

    assert evidence["E-001"]["verified"] is True
    assert evidence["LEGACY-001"]["reason"] == "기존 문자열 근거"
    assert find_issue_turn(debate["rounds"][0]["bull_response"], "growth")


def test_round_change_returns_selected_issue_and_round() -> None:
    debate = {
        "navigation": {
            "issues": [
                {
                    "issue_id": "growth",
                    "round_changes": [{"round": 2, "bull_change": "새 근거"}],
                }
            ]
        }
    }

    assert round_change(debate, "growth", 2)["bull_change"] == "새 근거"
    assert round_change(debate, "growth", 1) == {}


def test_collect_evidence_includes_regime_sources() -> None:
    debate = {
        "rounds": [],
        "regime_analysis": {
            "reasons": {
                "past_bull": [
                    {"evidence": [{"evidence_id": "RE-001", "verified": True}]}
                ]
            }
        },
    }

    assert collect_evidence(debate)["RE-001"]["verified"] is True
