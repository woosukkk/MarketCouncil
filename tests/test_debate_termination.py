import os
import sys
import types
import unittest


if "langgraph.graph" not in sys.modules:
    graph_module = types.ModuleType("langgraph.graph")
    graph_module.END = "END"
    graph_module.START = "START"
    graph_module.StateGraph = object
    langgraph_module = types.ModuleType("langgraph")
    langgraph_module.graph = graph_module
    sys.modules["langgraph"] = langgraph_module
    sys.modules["langgraph.graph"] = graph_module

if "openai" not in sys.modules:
    openai_module = types.ModuleType("openai")
    openai_module.OpenAI = object
    sys.modules["openai"] = openai_module

if "dotenv" not in sys.modules:
    dotenv_module = types.ModuleType("dotenv")
    dotenv_module.load_dotenv = lambda: None
    sys.modules["dotenv"] = dotenv_module

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from agents.analysis_debate_agent import AnalysisDebateAgent


def _response(
    claim: str = "기존 주장",
    evidence: list[str] | None = None,
    concession: str = "",
) -> dict:
    return {
        "issues": [{
            "issue_id": "ISSUE-1",
            "claim": claim,
            "evidence": [{"source_id": "S-1", "quote_id": value,
                          "citation_valid": True, "reason": "original"}
                         for value in (evidence or ["E-001"])],
            "concession": concession,
        }]
    }


class DebateTerminationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = object.__new__(AnalysisDebateAgent)

    def _state(self) -> dict:
        previous_response = _response()
        current_response = _response()
        return {
            "current_round": 2,
            "max_rounds": 3,
            "bull_response": current_response,
            "bear_response": current_response,
            "rounds": [
                {
                    "bull_response": previous_response,
                    "bear_response": previous_response,
                },
                {
                    "bull_response": current_response,
                    "bear_response": current_response,
                },
            ],
            "moderator_review": {
                "continue_debate": True,
                "issue_reviews": [{
                    "issue_id": "ISSUE-1",
                    "status": "CONTESTED",
                }],
            },
        }

    def test_stops_when_no_open_or_contested_issue_remains(self) -> None:
        state = self._state()
        state["moderator_review"]["issue_reviews"][0][
            "status"
        ] = "RESOLVED"

        self.assertEqual(self.agent.route_after_review(state), "summary")

    def test_stops_when_round_adds_no_information(self) -> None:
        state = self._state()

        self.assertEqual(self.agent.route_after_review(state), "summary")

    def test_continues_when_new_evidence_is_added(self) -> None:
        state = self._state()
        state["bull_response"] = _response(evidence=["E-001", "E-002"])
        state["rounds"][-1]["bull_response"] = state["bull_response"]

        self.assertEqual(
            self.agent.route_after_review(state),
            "next_round",
        )

    def test_minimum_and_maximum_round_guards_remain(self) -> None:
        state = self._state()
        state["current_round"] = 1
        self.assertEqual(
            self.agent.route_after_review(state),
            "next_round",
        )

        state["current_round"] = 3
        self.assertEqual(self.agent.route_after_review(state), "summary")

    def test_paraphrase_and_reason_changes_are_not_new_information(self) -> None:
        state = self._state()
        state["bull_response"] = _response(claim="A paraphrase", concession="None again")
        state["bull_response"]["issues"][0]["evidence"][0]["reason"] = "different wording"
        self.assertEqual(self.agent.route_after_review(state), "summary")

    def test_material_change_requires_explanation(self) -> None:
        state = self._state()
        review = state["moderator_review"]["issue_reviews"][0]
        review["material_change"] = True
        self.assertEqual(self.agent.route_after_review(state), "summary")
        review["change_reason"] = "Prior growth hypothesis withdrawn after margin comparison"
        self.assertEqual(self.agent.route_after_review(state), "next_round")

    def test_evidence_seen_in_older_round_is_not_new(self) -> None:
        state = self._state()
        state["rounds"].insert(0, {"bull_response": _response(evidence=["E-002"])})
        state["bull_response"] = _response(evidence=["E-002"])
        self.assertFalse(self.agent._has_new_information(state))

    def test_citation_validation_rejects_wrong_source_and_restores_original(self) -> None:
        response = _response(evidence=["Q1", "Q2"])
        response["issues"][0]["evidence"][0]["exact_quote"] = "fabricated"
        catalog = [{"source_id": "S-1", "quotes": [{"quote_id": "Q1", "text": "original"}]},
                   {"source_id": "S-2", "quotes": [{"quote_id": "Q2", "text": "other"}]}]
        result = self.agent._validate_citations(response, catalog)["issues"][0]
        self.assertEqual(len(result["evidence"]), 1)
        self.assertEqual(result["evidence"][0]["exact_quote"], "original")
        self.assertEqual(result["citation_errors"][0]["quote_id"], "Q2")

    def test_invalid_citation_cannot_extend_debate(self) -> None:
        state = self._state()
        state["bull_response"] = self.agent._validate_citations(_response(evidence=["fake"]), [])
        self.assertEqual(self.agent.route_after_review(state), "summary")

    def test_summary_receives_original_evidence_and_financial_data(self) -> None:
        from unittest.mock import Mock
        self.agent.moderator = Mock()
        self.agent.moderator.summarize.return_value = {}
        state = self._state()
        state["financial_data"] = {"revenue": 100}
        state["evidence_catalog"] = [{"source_id": "S-1", "quotes": []}]
        self.agent.summarize(state)
        payload = self.agent.moderator.summarize.call_args.args[0]
        self.assertEqual(payload["financial_data"], state["financial_data"])
        self.assertEqual(payload["evidence_catalog"], state["evidence_catalog"])


if __name__ == "__main__":
    unittest.main()
