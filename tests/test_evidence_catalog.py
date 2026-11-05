from tools.debate_transcript_renderer import DebateTranscriptRenderer
from tools.evidence_catalog import EvidenceCatalog
from agents.analysis_debate_agent import PARTICIPANT_SCHEMA


def test_resolve_links_verified_quote_to_source_paragraph() -> None:
    catalog = [
        {
            "source_id": "RAG-001",
            "source_type": "regulatory_filing",
            "title": "테스트 공시",
            "source_url": "https://example.com/filing",
            "published_at": "2026-08-01",
            "document_id": "doc-1",
            "chunk_id": "7",
            "page_number": 4,
            "content": "앞 문단입니다.\n\n매출은 전년 대비 증가했습니다. 이익도 증가했습니다.\n\n뒤 문단입니다.",
            "quotes": [
                {"quote_id": "RAG-001-Q01", "text": "매출은 전년 대비 증가했습니다."}
            ],
        }
    ]
    debate = {
        "company_name": "테스트기업",
        "agenda": [{"issue_id": "growth", "title": "성장", "question": "성장했는가?"}],
        "rounds": [
            {
                "round": 1,
                "bull_response": {
                    "issues": [
                        {
                            "issue_id": "growth",
                            "claim": "성장했다.",
                            "target_claim": "",
                            "response": "",
                            "evidence": [
                                {
                                    "source_id": "RAG-001",
                                    "quote_id": "RAG-001-Q01",
                                    "reason": "매출 증가를 직접 확인한다.",
                                }
                            ],
                            "example_or_data": "",
                            "concession": "",
                            "missing_evidence": "",
                        }
                    ]
                },
                "bear_response": {"issues": []},
                "moderator_review": {"issue_reviews": []},
            }
        ],
        "moderator_summary": {},
        "stop_reason": "테스트 종료",
    }

    resolved = EvidenceCatalog.resolve(debate, catalog)
    evidence = resolved["rounds"][0]["bull_response"]["issues"][0]["evidence"][0]
    markdown = DebateTranscriptRenderer().render(resolved)

    assert evidence["verified"] is True
    assert evidence["exact_quote"] == "매출은 전년 대비 증가했습니다."
    assert evidence["context_text"] == "매출은 전년 대비 증가했습니다. 이익도 증가했습니다."
    assert "[E-001](#evidence-e-001)" in markdown
    assert "[외부 원문 열기](https://example.com/filing#page=4)" in markdown
    assert "인용 문단 전체" in markdown


def test_resolve_rejects_quote_missing_from_source() -> None:
    debate = {
        "rounds": [
            {
                "bull_response": {
                    "issues": [
                        {
                            "evidence": [
                                {
                                    "source_id": "RAG-001",
                                    "exact_quote": "원문에 없는 문장",
                                    "reason": "검증 실패 테스트",
                                }
                            ]
                        }
                    ]
                },
                "bear_response": {"issues": []},
            }
        ]
    }
    catalog = [{"source_id": "RAG-001", "content": "실제 원문"}]

    resolved = EvidenceCatalog.resolve(debate, catalog)
    evidence = resolved["rounds"][0]["bull_response"]["issues"][0]["evidence"][0]

    assert evidence["verified"] is False
    assert evidence["context_text"] == ""


def test_prompt_catalog_exposes_quote_ids_without_full_content() -> None:
    catalog = EvidenceCatalog.build(
        financial_data={"ticker": "TEST", "price_date": "2026-08-01"},
        retrieved_chunks=[
            {
                "source": "report.pdf",
                "chunk_id": 3,
                "text": "첫 문장입니다. 매출은 전년 대비 증가했습니다. 마지막 문장입니다.",
                "metadata": {
                    "document_id": "doc-1",
                    "source_url": "https://example.com/report.pdf",
                    "page_number": 7,
                },
            }
        ],
        web_documents=[],
    )

    prompt_catalog = EvidenceCatalog.for_prompt(catalog)
    report = next(item for item in prompt_catalog if item["source_id"] == "RAG-001")

    assert "content" not in report
    assert report["quotes"]
    assert report["quotes"][0]["quote_id"].startswith("RAG-001-Q")


def test_unknown_quote_id_is_not_verified() -> None:
    catalog = [
        {
            "source_id": "RAG-001",
            "content": "실제 원문 문장입니다.",
            "quotes": [{"quote_id": "RAG-001-Q01", "text": "실제 원문 문장입니다."}],
        }
    ]

    evidence = EvidenceCatalog.resolve_quote(
        {"source_id": "RAG-001", "quote_id": "RAG-001-Q99", "reason": "테스트"},
        catalog,
        "E-001",
    )
    item_schema = PARTICIPANT_SCHEMA["properties"]["issues"]["items"]["properties"]["evidence"]["items"]

    assert evidence["verified"] is False
    assert evidence["exact_quote"] == ""
    assert "quote_id" in item_schema["required"]
    assert "exact_quote" not in item_schema["properties"]
