import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"


class DebateWebTest(unittest.TestCase):
    def test_navigation_and_evidence_selection(self) -> None:
        """An evidence click must override filters and follow the current scope."""
        debate = {
            "company_name": "테스트 기업",
            "agenda": [{"issue_id": value, "title": value} for value in ("A", "B")],
            "rounds": [],
            "moderator_summary": {"summary": "추가 데이터 필요"},
        }
        for number in (1, 2):
            debate["rounds"].append({
                "round": number,
                "bull_response": {"issues": [{
                    "issue_id": issue,
                    "claim": f"{issue} 라운드 {number}",
                    "evidence": [{
                        "evidence_id": f"{issue}-{number}-{index}",
                        "exact_quote": f"인용 {issue}-{number}-{index}",
                        "verified": index == 1,
                    } for index in (1, 2)],
                } for issue in ("A", "B")]},
            })

        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "analysis_debate_first.json"
            second = Path(directory) / "analysis_debate_second.json"
            first.write_text(json.dumps(debate), encoding="utf-8")
            second.write_text(json.dumps({**debate, "company_name": "다른 기업"}), encoding="utf-8")
            with patch("app.debate_view_data.list_debate_files", return_value=[first, second]):
                app = AppTest.from_file(str(APP), default_timeout=30).run()
                self.assertFalse(app.exception)
                self.assertEqual(app.get("button_group")[0].value, "토론 탐색")
                app.selectbox(key="evidence_filter").select("인용 대조 완료").run()
                self.assertEqual(app.selectbox(key="selected_evidence_id").options, ["A-1-1"])
                app.button(key="bull_A_1_1_A-1-2").click().run()
                self.assertFalse(app.exception)
                self.assertEqual(app.selectbox(key="selected_evidence_id").value, "A-1-2")
                self.assertEqual(app.selectbox(key="evidence_filter").value, "전체")

                app.get("button_group")[1].set_value(2).run()
                self.assertEqual(app.selectbox(key="selected_evidence_id").options, ["A-2-1", "A-2-2"])
                app.radio[0].set_value("B").run()
                self.assertEqual(app.selectbox(key="selected_evidence_id").options, ["B-2-1", "B-2-2"])
                app.selectbox(key="debate_session").select(second).run()
                self.assertEqual(app.selectbox(key="selected_evidence_id").options, ["A-1-1", "A-1-2"])
                self.assertTrue(any("다른 기업" in title.value for title in app.title))

                app.get("button_group")[0].set_value("최종 정리").run()
                self.assertTrue(any(item.value == "추가 데이터 필요" for item in app.markdown))
                app.get("button_group")[0].set_value("시장 국면").run()
                self.assertTrue(any("시장 국면 비교 데이터가 없습니다" in item.value for item in app.info))
                self.assertFalse(app.exception)

    def test_no_saved_results(self) -> None:
        with patch("app.debate_view_data.list_debate_files", return_value=[]):
            app = AppTest.from_file(str(APP), default_timeout=30).run()
            self.assertFalse(app.exception)
            self.assertTrue(any("첫 번째 투자 토론" in title.value for title in app.title))


if __name__ == "__main__":
    unittest.main()
