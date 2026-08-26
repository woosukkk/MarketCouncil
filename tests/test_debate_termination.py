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
            "evidence": evidence or ["E-001"],
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


if __name__ == "__main__":
    unittest.main()
