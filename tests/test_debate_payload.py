"""Offline payload contracts: stable evidence, exact quote identity and no mutation."""
import copy
import json
import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("OPENAI_API_KEY", "offline-test-key")

from agents.analysis_debate_agent import AnalysisDebateAgent, PARTICIPANT_SCHEMA
from agents.moderator_agent import ModeratorAgent, REVIEW_SCHEMA
from tools.debate_payload import DYNAMIC_SECTION, debate_payload


class DebatePayloadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = [{"source_id": "S1", "quotes": [{"quote_id": "Q1", "text": '매출 100억원. "인용"\n다음 줄'}]}]
        self.common = "고정 근거\n" + json.dumps(self.catalog, ensure_ascii=False, indent=2)
        self.citation = {"source_id": "S1", "quote_id": "Q1", "exact_quote": self.catalog[0]["quotes"][0]["text"], "reason": "수치 직접 대조", "citation_valid": True}

    def decode(self, value: str) -> dict:
        return json.loads(value.rsplit(DYNAMIC_SECTION, 1)[1])

    def test_shared_prefix_stays_byte_identical_when_round_changes(self) -> None:
        inputs = [debate_payload(self.common, {"round": number}, self.catalog) for number in (1, 2)]
        self.assertTrue(all(value.startswith(self.common + DYNAMIC_SECTION) for value in inputs))
        self.assertEqual([self.decode(value) for value in inputs], [{"round": 1}, {"round": 2}])
        self.assertEqual(inputs[0].count(self.common), 1)

    def test_exact_duplicates_are_removed_recursively_without_changing_saved_data(self) -> None:
        dynamic = {"rounds": [{"issues": [{"evidence": [self.citation]}]}]}
        original = copy.deepcopy(dynamic)
        value = self.decode(debate_payload(self.common, dynamic, self.catalog))
        actual = value["rounds"][0]["issues"][0]["evidence"][0]
        self.assertEqual(actual, {name: item for name, item in self.citation.items() if name != "exact_quote"})
        self.assertEqual(dynamic, original)
        self.assertEqual(self.catalog[0]["quotes"][0]["text"], self.citation["exact_quote"])

    def test_wrong_source_quote_text_or_invalid_identifier_preserves_exact_quote(self) -> None:
        for changed in ({"source_id": "S2"}, {"quote_id": "Q2"}, {"exact_quote": "다른 원문"}, {"source_id": ["S1"]}):
            with self.subTest(changed=changed):
                citation = {**self.citation, **changed}
                self.assertEqual(self.decode(debate_payload(self.common, citation, self.catalog)), citation)

    def test_catalog_absent_from_actual_input_never_discards_quote(self) -> None:
        self.assertEqual(self.decode(debate_payload("원문 없는 입력", self.citation, self.catalog)), self.citation)
        self.assertEqual(self.decode(debate_payload(self.common, self.citation, [])), self.citation)

    def test_conflicting_duplicate_ids_keep_quote_for_review(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog[0]["quotes"].append({"quote_id": "Q1", "text": "서로 다른 원문"})
        common = json.dumps(catalog, ensure_ascii=False, indent=2)
        self.assertEqual(self.decode(debate_payload(common, self.citation, catalog)), self.citation)

    def test_participant_uses_prefix_and_keeps_catalog_and_output_schema(self) -> None:
        agent = object.__new__(AnalysisDebateAgent)
        agent.client = Mock()
        state = {"current_round": 2, "analysis_as_of": "2026-10-16", "debate_input": self.common,
                 "evidence_catalog": self.catalog, "rounds": [], "bull_response": {"evidence": [self.citation]}}
        original = copy.deepcopy(state)
        with patch("agents.analysis_debate_agent.structured_response", return_value={}) as call:
            agent._participant_response("bear", state)
        encoded = call.call_args.args[2]
        self.assertTrue(encoded.startswith(self.common + DYNAMIC_SECTION))
        self.assertNotIn("original_evidence_and_analysis", self.decode(encoded))
        self.assertNotIn("exact_quote", self.decode(encoded)["current_opponent_response"]["evidence"][0])
        self.assertIs(call.call_args.args[4], PARTICIPANT_SCHEMA)
        self.assertEqual(state, original)

    def test_moderator_receives_same_catalog_once_and_preserves_review_schema(self) -> None:
        moderator = ModeratorAgent(Mock())
        payload = {"original_evidence_and_analysis": self.common, "evidence_catalog": self.catalog,
                   "round": 2, "bull_response": {"evidence": [self.citation]}}
        original = copy.deepcopy(payload)
        with patch.object(moderator, "_respond", return_value={}) as call:
            moderator.review_round(payload)
        encoded = call.call_args.args[1]
        dynamic = self.decode(encoded)
        self.assertTrue(encoded.startswith(self.common + DYNAMIC_SECTION))
        self.assertNotIn("evidence_catalog", dynamic)
        self.assertNotIn("original_evidence_and_analysis", dynamic)
        self.assertNotIn("exact_quote", dynamic["bull_response"]["evidence"][0])
        self.assertIs(call.call_args.args[3], REVIEW_SCHEMA)
        self.assertEqual(payload, original)


if __name__ == "__main__":
    unittest.main()
