"""Offline contract tests for quality checks inside the real debate agent."""
import copy
import json
import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("OPENAI_API_KEY", "offline-test-key")

from agents.analysis_debate_agent import AnalysisDebateAgent
from tools.debate_payload import DYNAMIC_SECTION


class DebateQualityIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = object.__new__(AnalysisDebateAgent)
        self.agent.client = Mock(name="offline_client")
        self.agent.moderator = Mock(name="offline_moderator")
        self.agent.max_rounds = 3

    def source(self, identifier: str = "S1", quote: str = "매출이 12% 증가했다", published: str = "2026-10-01") -> dict:
        return {"source_id": identifier, "published_at": published, "content": quote,
                "quotes": [{"quote_id": "Q1", "text": quote}]}

    def response(self, claim: str = "매출이 12% 증가했다", source: str = "S1", missing: str = "") -> dict:
        return {"position_summary": "가상 분석", "issues": [{
            "issue_id": "ISSUE-1", "claim": claim, "target_claim": "", "response": "",
            "warrant": "", "qualifier": "", "example_or_data": "", "concession": "",
            "missing_evidence": missing, "evidence": [{"source_id": source, "quote_id": "Q1", "reason": "인용 확인"}],
        }]}

    def state(self, catalog: list[dict] | None = None) -> dict:
        return {"analysis_as_of": "2026-10-15", "debate_input": "가상 원문과 분석",
                "current_round": 2, "max_rounds": 3,
                "agenda": [{"issue_id": "ISSUE-1", "title": "매출 검토"}],
                "financial_data": {"price_date": "2026-10-10"},
                "evidence_catalog": catalog if catalog is not None else [self.source()],
                "rounds": [], "bull_response": {}, "bear_response": {},
                "moderator_review": {"continue_debate": True, "issue_reviews": [
                    {"issue_id": "ISSUE-1", "status": "CONTESTED", "material_change": False, "change_reason": ""}]}}

    def run_args(self) -> dict:
        return {"company_name": "가상기업", "financial_data": {"price_date": "2026-10-10", "ticker": "TEST"},
                "bull_result": "상승 가설", "bear_result": "하락 가설", "sentiment_summary": {},
                "evidence_catalog": [self.source()], "as_of_date": "2026-10-14T15:30:00Z"}

    def test_participant_numeric_warning_reaches_missing_evidence(self) -> None:
        raw = self.response("매출이 15% 증가했다", missing="분기별 비교 필요")
        with patch("agents.analysis_debate_agent.structured_response", return_value=raw) as generate:
            issue = self.agent._participant_response("bull", self.state())["issues"][0]
        self.assertEqual(issue["citation_quality"]["identity_status"], "matched")
        self.assertEqual(issue["citation_quality"]["numeric_status"], "needs_review")
        self.assertEqual(issue["citation_quality"]["semantic_status"], "not_evaluated")
        self.assertIn("number_not_in_quotes", issue["citation_quality"]["warnings"])
        self.assertIn("분기별 비교 필요", issue["missing_evidence"])
        self.assertIn("핵심 수치를 직접 확인할 수 있는 인용문 추가 필요", issue["missing_evidence"])
        self.assertTrue(issue["evidence"][0]["citation_valid"])
        self.assertEqual(json.loads(generate.call_args.args[2].rsplit(DYNAMIC_SECTION, 1)[1])["analysis_as_of"], "2026-10-15")

    def test_matched_identity_and_number_do_not_assert_semantic_truth(self) -> None:
        raw = self.response("매출이 30% 감소했다")
        result = self.agent._validate_citations(raw, [self.source(quote="매출이 30% 증가했다")], "2026-10-15")
        quality = result["issues"][0]["citation_quality"]
        self.assertEqual(quality["identity_status"], "matched")
        self.assertEqual(quality["numeric_status"], "values_present")
        self.assertEqual(quality["semantic_status"], "not_evaluated")
        self.assertNotIn("number_not_in_quotes", quality["warnings"])
        self.assertNotIn("semantic_valid", result["issues"][0])

    def test_future_citation_is_excluded_and_cannot_extend_debate(self) -> None:
        catalog = [self.source(), self.source("FUTURE", published="2026-10-16")]
        previous = self.agent._validate_citations(self.response(), catalog, "2026-10-15")
        current = self.agent._validate_citations(self.response(source="FUTURE"), catalog, "2026-10-15")
        issue = current["issues"][0]
        self.assertEqual(issue["evidence"], [])
        self.assertIn("future_source", issue["citation_quality"]["warnings"])
        self.assertEqual(issue["citation_quality"]["identity_status"], "matched")
        self.assertIn("분석 기준일 이후", issue["citation_errors"][0]["error"])
        self.assertIn("분석 기준일 이후 자료를 제외", issue["missing_evidence"])
        state = self.state(catalog)
        state.update(bull_response=current, bear_response=previous, rounds=[
            {"bull_response": previous, "bear_response": previous},
            {"bull_response": current, "bear_response": previous},
        ])
        self.assertFalse(self.agent._has_new_information(state))
        self.assertEqual(self.agent.route_after_review(state), "summary")

    def test_old_historical_fact_is_retained_for_short_term_research(self) -> None:
        quote = "2020년 매출은 1조원이었다."
        claim = "향후 1~4주를 검토할 때 2020년 매출 1조원이라는 역사적 사실을 참고한다."
        issue = self.agent._validate_citations(self.response(claim), [self.source(quote=quote, published="2020-12-31")], "2026-10-15")["issues"][0]
        self.assertTrue(issue["evidence"][0]["citation_valid"])
        self.assertEqual(issue["citation_quality"]["numeric_status"], "values_present")
        self.assertNotIn("stale_forecast", issue["citation_quality"]["warnings"])
        self.assertEqual(issue["missing_evidence"], "")

    def test_date_and_stale_forecast_warnings_reach_missing_evidence(self) -> None:
        for published, code, note in [
            ("", "source_date_missing", "근거 자료의 게시일 확인 필요"),
            ("2026-01-01", "stale_forecast", "단기 전망의 기간에 맞는 최신 근거 추가 필요"),
        ]:
            with self.subTest(published=published):
                issue = self.agent._validate_citations(self.response("향후 1~4주 매출 전망"), [self.source(quote="매출 증가를 전망한다", published=published)], "2026-10-15")["issues"][0]
                self.assertIn(code, issue["citation_quality"]["warnings"])
                self.assertIn(note, issue["missing_evidence"])
                self.assertTrue(issue["evidence"][0]["citation_valid"])

    def test_run_normalizes_as_of_before_building_input_and_graph_state(self) -> None:
        self.agent.graph = Mock()
        self.agent.graph.invoke.return_value = {"rounds": []}
        args = self.run_args()
        original = copy.deepcopy(args)
        with patch.object(self.agent, "_build_input", wraps=self.agent._build_input) as build:
            result = self.agent.run(**args)
        self.assertEqual(build.call_args.kwargs["analysis_as_of"], "2026-10-15")
        state = self.agent.graph.invoke.call_args.args[0]
        self.assertEqual(state["analysis_as_of"], "2026-10-15")
        self.assertIn("분석 기준일: 2026-10-15", state["debate_input"])
        self.assertEqual(state["financial_data"]["price_date"], "2026-10-10")
        self.assertEqual(result["analysis_as_of"], "2026-10-15")
        self.assertEqual(args, original)

    def test_real_graph_propagates_as_of_to_all_participants_and_moderator(self) -> None:
        self.agent.max_rounds = 2
        self.agent.moderator.create_agenda.return_value = {"agenda": [{"issue_id": "ISSUE-1", "title": "매출 검토"}]}
        self.agent.moderator.review_round.side_effect = lambda payload: {
            "continue_debate": False,
            "issue_reviews": [{"issue_id": "ISSUE-1", "status": "CONTESTED", "material_change": False, "change_reason": ""}],
        }
        self.agent.moderator.summarize.return_value = {"summary": "가상 최종 정리"}
        self.agent.graph = self.agent._build_graph()
        with patch("agents.analysis_debate_agent.structured_response", side_effect=lambda *args: self.response()) as generate:
            result = self.agent.run(**self.run_args())
        self.assertEqual(len(result["rounds"]), 2)
        self.assertEqual(result["analysis_as_of"], "2026-10-15")
        self.assertEqual(generate.call_count, 4)
        self.assertEqual([call.args[3] for call in generate.call_args_list], ["bull_debate_turn", "bear_debate_turn"] * 2)
        for call in generate.call_args_list:
            common, raw_state = call.args[2].rsplit(DYNAMIC_SECTION, 1)
            self.assertEqual(json.loads(raw_state)["analysis_as_of"], "2026-10-15")
            self.assertIn("분석 기준일: 2026-10-15", common)
        self.assertEqual(self.agent.moderator.review_round.call_count, 2)
        for call in self.agent.moderator.review_round.call_args_list:
            self.assertEqual(call.args[0]["analysis_as_of"], "2026-10-15")
            self.assertIn("분석 기준일: 2026-10-15", call.args[0]["original_evidence_and_analysis"])
        summary = self.agent.moderator.summarize.call_args.args[0]
        self.assertEqual(summary["analysis_as_of"], "2026-10-15")
        self.assertEqual(summary["financial_data"]["price_date"], "2026-10-10")
        self.assertEqual(len(summary["rounds"]), 2)

    def test_invalid_as_of_stops_before_build_input_or_graph_invocation(self) -> None:
        self.agent.graph = Mock()
        for as_of in ("not-a-date", "2026-02-30", "2026-10-15invalid", "2026-10-15T00:00:00", ""):
            with self.subTest(as_of=as_of), patch.object(self.agent, "_build_input") as build:
                with self.assertRaises(ValueError):
                    self.agent.run(**{**self.run_args(), "as_of_date": as_of})
                build.assert_not_called()
        self.agent.graph.invoke.assert_not_called()


if __name__ == "__main__":
    unittest.main()
