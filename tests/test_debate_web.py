import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import Future

import streamlit as st
from streamlit.testing.v1 import AppTest
from app.debate_view_data import ordered_agenda


APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"


class DebateWebTest(unittest.TestCase):
    def test_editorial_priority_and_article_navigation(self) -> None:
        debate = {
            "company_name": "기사 테스트",
            "agenda": [{"issue_id": "A", "title": "첫 의제"}, {"issue_id": "B", "title": "둘째 의제"}],
            "rounds": [{"round": 1}],
            "moderator_summary": {"headline": "기대는 유지되지만 근거 확인 필요",
                                  "lead": "단기 지표가 부족합니다.",
                                  "priority_issue_ids": ["B", "missing", "B"]},
        }
        self.assertEqual([item["issue_id"] for item in ordered_agenda(debate)], ["B", "A"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "analysis_debate_editorial.json"
            path.write_text(json.dumps(debate), encoding="utf-8")
            with patch("app.debate_view_data.list_debate_files", return_value=[path]):
                app = AppTest.from_file(str(APP), default_timeout=30).run()
                self.assertTrue(any(item.value == debate["moderator_summary"]["headline"] for item in app.header))
                app.button(key="featured_article").click().run()
                self.assertEqual(app.radio(key=f"issue_{path}").value, "B")
                app.button(key="back_to_articles").click().run()
                app.button(key="article_1").click().run()
                self.assertEqual(app.radio(key=f"issue_{path}").value, "A")
                self.assertTrue(any(item.value == "첫 의제" for item in app.header))
                self.assertFalse(app.exception)

    def test_launch_pending_completion_and_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result_path = Path(directory) / "analysis_debate_new.json"
            result_path.write_text(json.dumps({"company_name": "새 분석"}), encoding="utf-8")
            future: Future[Path] = Future()
            st.cache_resource.clear()
            self.addCleanup(st.cache_resource.clear)
            with patch("app.web_analysis_runner.AnalysisRunner") as runner_class, patch(
                "app.debate_view_data.list_debate_files", return_value=[]
            ) as files:
                runner = runner_class.return_value
                runner.current.return_value = ("", None)

                def start(company: str) -> None:
                    runner.current.return_value = (company, future)

                runner.start.side_effect = start
                app = AppTest.from_file(str(APP), default_timeout=30).run()
                self.assertFalse(any(button.key == "start_analysis" for button in app.button))
                app.radio(key="workspace_page").set_value("새 분석").run()
                app.button(key="start_analysis").click().run()
                runner.start.assert_called_once_with("삼성전자")
                self.assertTrue(app.button(key="start_analysis").disabled)
                self.assertFalse(app.exception)

                files.return_value = [result_path]
                future.set_result(result_path)
                app.run()
                self.assertEqual(app.selectbox(key="debate_session").value, result_path)
                self.assertTrue(any("새 분석" in title.value for title in app.title))
                self.assertEqual(app.radio(key="workspace_page").value, "토론 보기")
                self.assertFalse(any(button.key == "start_analysis" for button in app.button))
                self.assertFalse(app.exception)

                failed: Future[Path] = Future()
                failed.set_exception(RuntimeError("테스트 API 실패"))
                runner.current.return_value = ("삼성전자", failed)
                app.radio(key="workspace_page").set_value("새 분석").run()
                self.assertTrue(any("분석 실패" in error.value for error in app.error))
                self.assertFalse(app.button(key="start_analysis").disabled)
                self.assertFalse(app.exception)

    def test_navigation_and_evidence_selection(self) -> None:
        """An evidence click must override filters and follow the current scope."""
        debate = {
            "company_name": "테스트 기업",
            "agenda": [{"issue_id": value, "title": value} for value in ("A", "B")],
            "rounds": [],
            "moderator_summary": {"summary": "추가 데이터 필요"},
            "navigation": {"issues": [{"issue_id": "A", "round_changes": [{
                "round": 1, "new_evidence_ids": ["A-1-1"],
                "concessions": ["수요 증가 인정"], "remaining_question": "현금흐름 확인 필요",
            }]}]},
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
                        "title": "공식 실적 보고서",
                        "published_at": "2026-08-01",
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
                self.assertTrue(any(item.value == "토론 한눈에 보기" for item in app.subheader))
                app.button(key="featured_article").click().run()
                self.assertEqual(app.button(key="bull_A_1_0_A-1-1").label, "공식 실적 보고서")
                self.assertTrue(any("2026-08-01" in item.value for item in app.caption))
                self.assertTrue(any(item.value == "현금흐름 확인 필요" for item in app.markdown))
                app.selectbox(key="evidence_filter").select("인용 대조 완료").run()
                self.assertEqual(app.selectbox(key="selected_evidence_id").options, ["A-1-1"])
                app.button(key="bull_A_1_1_A-1-2").click().run()
                self.assertFalse(app.exception)
                self.assertEqual(app.selectbox(key="selected_evidence_id").value, "A-1-2")
                self.assertEqual(app.selectbox(key="evidence_filter").value, "전체")

                app.get("button_group")[1].set_value(2).run()
                self.assertEqual(app.selectbox(key="selected_evidence_id").options, ["A-2-1", "A-2-2"])
                app.radio(key=f"issue_{first}").set_value("B").run()
                self.assertEqual(app.selectbox(key="selected_evidence_id").options, ["B-2-1", "B-2-2"])
                app.selectbox(key="debate_session").select(second).run()
                app.button(key="featured_article").click().run()
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
