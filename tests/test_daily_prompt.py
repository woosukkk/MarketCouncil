import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from desktop import daily_official as daily
from desktop import daily_history as history


class HistoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.data = Path(self.folder.name)
        self.day = "2026-11-09"

    def write(self, name: str, value: object) -> None:
        path = self.data / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")

    def rows(self, running: bool = False) -> dict:
        rows, warnings = history.load_history(self.data, self.day, running)
        self.assertEqual(warnings, [])
        return {row["day"]: row for row in rows}

    def test_history_keeps_each_day_and_only_allowlisted_fields(self) -> None:
        with patch.object(daily, "DATA", self.data):
            daily.save_state({"day": "2026-11-08", "status": "completed", "result_path": "private/result.json", "secret": "private-key"})
            daily.save_state({"day": self.day, "status": "pending_upload", "analysis_attempts": 2, "target": {"company_name": "Apple", "private": "private-document"}})
        rows = self.rows()
        self.assertEqual(rows["2026-11-08"]["label"], "공식 게시 완료")
        self.assertEqual(rows[self.day]["company"], "Apple")
        stored = (self.data / "history" / "2026-11-08.json").read_text(encoding="utf-8")
        self.assertNotIn("private", stored)
        self.assertTrue(json.loads(stored)["result_saved"])

    def test_first_day_rollover_preserves_legacy_latest_state(self) -> None:
        self.write("state.json", {"day": "2026-11-08", "status": "completed", "target": {"company_name": "Apple"}})
        with patch.object(daily, "DATA", self.data):
            daily.save_state({"day": self.day, "status": "attempting", "analysis_attempts": 1})
        self.assertEqual(self.rows()["2026-11-08"]["status"], "completed")
        self.assertEqual(self.rows()["2026-11-08"]["company"], "Apple")

    def test_checkpoint_is_not_a_publication_receipt(self) -> None:
        (self.data / "analysis-2026-11-07-a1b2-c3d4.json").write_text("private original never parsed")
        row = self.rows()["2026-11-07"]
        self.assertEqual(row["status"], "checkpoint")
        self.assertIn("미확인", row["label"])

    def test_failure_is_deduplicated_and_does_not_override_later_success(self) -> None:
        error = {"day": self.day, "stage": "analysis", "error_type": "RuntimeError", "causes": [{"api_code": "credit_balance_exhausted"}]}
        self.write("errors/first.json", error)
        self.write("last-error.json", error)
        self.write("state.json", {"day": self.day, "status": "completed"})
        row = self.rows()[self.day]
        self.assertEqual(row["status"], "completed")
        self.assertEqual(len(row["errors"]), 1)
        self.assertIn("잔액 소진", history.failure_text(row["errors"][0]))

    def test_interrupted_and_running_are_distinguished_by_live_lock(self) -> None:
        self.write("state.json", {"day": self.day, "status": "attempting", "analysis_attempts": 1})
        self.assertIn("중단됨", self.rows()[self.day]["label"])
        self.assertEqual(self.rows(True)[self.day]["label"], "실행 중")

    def test_early_failure_retains_recovery_count_and_saved_result(self) -> None:
        self.write("state.json", {"day": self.day, "status": "pending_upload", "analysis_attempts": 2, "result_path": "saved.json"})
        history.record_run(self.data, {"day": self.day, "status": "failed"}, "account")
        row = self.rows()[self.day]
        self.assertEqual(row["analysis_attempts"], 2)
        self.assertTrue(row["result_saved"])
        self.assertEqual(row["status"], "failed")
        self.assertEqual(history.run_action(row, False, True), ("저장된 오늘 결과 게시 재시도", True))

    def test_error_before_analysis_still_appears_in_history(self) -> None:
        self.write("last-error.json", {"day": self.day, "stage": "credentials", "error_type": "FileNotFoundError"})
        row = self.rows()[self.day]
        self.assertEqual(row["status"], "failed")
        self.assertIn("설정 파일 없음", history.failure_text(row["errors"][0]))

    def test_corrupt_and_invalid_metadata_does_not_crash_history(self) -> None:
        (self.data / "state.json").write_text("{bad", encoding="utf-8")
        self.write("history/unknown.json", {"day": "2026-99-99", "status": []})
        rows, warnings = history.load_history(self.data, self.day, False)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(rows[0]["status"], "not_run")
        self.assertEqual(history.state_summary({"status": []})["status"], "failed")

    def test_new_day_never_inherits_yesterdays_result_or_company_after_failure(self) -> None:
        self.write("state.json", {"day": "2026-11-08", "status": "completed", "analysis_attempts": 2, "result_path": "yesterday.json", "target": {"company_name": "Apple"}})
        with patch.object(daily, "DATA", self.data), patch.object(daily, "today", return_value=self.day), patch.object(daily, "credentials", return_value={}), patch.object(daily, "source_version", return_value="test"), patch.object(daily, "run_once", side_effect=RuntimeError("private message")), patch.object(daily, "notify"):
            self.assertEqual(daily.run(), 1)
        today = self.rows()[self.day]
        self.assertFalse(today["result_saved"])
        self.assertEqual(today["company"], "")
        self.assertEqual(today["analysis_attempts"], 0)

    def test_already_published_new_day_does_not_copy_old_company(self) -> None:
        self.write("state.json", {"day": "2026-11-08", "status": "completed", "target": {"company_name": "Apple"}})
        with patch.object(daily, "DATA", self.data), patch.object(daily, "today", return_value=self.day), patch.object(daily, "credentials", return_value={}), patch.object(daily, "source_version", return_value="test"), patch.object(daily, "run_once", side_effect=daily.AlreadyPublished()), patch.object(daily, "notify"):
            self.assertEqual(daily.run(), 0)
        self.assertEqual(self.rows()[self.day]["company"], "")
        self.assertEqual(self.rows()[self.day]["status"], "completed")

    def test_failure_details_never_echo_raw_exception_or_credentials(self) -> None:
        error = {"stage": "analysis", "error_type": "RuntimeError", "message": "private token", "causes": [{"type": "IncompleteResponseError", "incomplete_reason": "max_output_tokens", "body": "private prompt"}]}
        text = history.failure_text(error)
        self.assertIn("출력 토큰", text)
        self.assertNotIn("private", text)
        self.assertIn("정확한 원인은 확인할 수 없습니다", history.failure_text({"error_type": "RuntimeError"}))

    def test_action_never_offers_completed_or_capped_or_concurrent_analysis(self) -> None:
        self.assertFalse(history.run_action({"status": "completed"}, False, True)[1])
        self.assertFalse(history.run_action({"status": "not_run"}, True, True)[1])
        self.assertFalse(history.run_action({"status": "not_run"}, False, False)[1])
        self.assertFalse(history.run_action({"status": "analysis_failed", "analysis_attempts": 2}, False, True)[1])
        self.assertTrue(history.run_action({"status": "analysis_failed", "analysis_attempts": 1}, False, True)[1])

    @unittest.skipUnless(os.name == "nt", "Windows file locking")
    def test_live_lock_probe_does_not_change_or_steal_run_lock(self) -> None:
        import msvcrt
        lock = self.data / "run.lock"
        lock.write_bytes(b"0")
        self.assertFalse(history.is_running(self.data))
        with lock.open("r+b") as handle:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            try:
                self.assertTrue(history.is_running(self.data))
            finally:
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        self.assertEqual(lock.read_bytes(), b"0")


@unittest.skipUnless(os.name == "nt", "Windows startup window")
class PromptTests(unittest.TestCase):
    def setUp(self) -> None:
        import tkinter as tk
        from desktop import daily_prompt
        self.module = daily_prompt
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.data = Path(self.folder.name)
        (self.data / "credentials.dpapi").touch()
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.patchers = [patch.object(daily, "DATA", self.data), patch.object(daily, "today", return_value="2026-11-09"), patch.object(daily_prompt, "is_running", return_value=False), patch.object(daily_prompt.subprocess, "Popen")]
        mocks = [item.start() for item in self.patchers]
        for item in self.patchers:
            self.addCleanup(item.stop)
        self.launch = mocks[-1]
        self.launch.return_value.poll.return_value = None
        self.window = daily_prompt.DailyPrompt(self.root)

    def test_open_refresh_and_close_do_not_start_any_paid_work(self) -> None:
        self.window.refresh()
        self.launch.assert_not_called()
        self.assertEqual(self.window.table.item("2026-11-09", "values")[2], "미실행")

    def test_explicit_click_launches_once_and_disables_second_click(self) -> None:
        self.window.start()
        self.window.start()
        self.launch.assert_called_once()
        self.assertEqual(self.launch.call_args.args[0], daily.launch_command())
        self.assertEqual(str(self.window.run_button["state"]), "disabled")

    def test_completed_day_cannot_launch_from_window(self) -> None:
        daily.save_state({"day": "2026-11-09", "status": "completed"})
        self.window.start()
        self.launch.assert_not_called()

    def test_unreadable_metadata_blocks_launch_and_explains_problem(self) -> None:
        (self.data / "state.json").write_text("broken", encoding="utf-8")
        self.window.start()
        self.launch.assert_not_called()
        self.assertIn("기록을 읽을 수 없습니다", self.window.details.get("1.0", "end"))

    def test_unreadable_old_error_warns_without_blocking_todays_run(self) -> None:
        (self.data / "errors").mkdir()
        (self.data / "errors" / "old.json").write_text("broken", encoding="utf-8")
        self.window.start()
        self.launch.assert_called_once()
        self.assertIn("old.json", self.window.details.get("1.0", "end"))

    def test_launch_error_is_reported_without_exposing_exception(self) -> None:
        self.launch.side_effect = OSError("private path and key")
        with patch.object(self.module.messagebox, "showerror") as alert:
            self.window.start()
        alert.assert_called_once()
        self.assertNotIn("private", str(alert.call_args))


if __name__ == "__main__":
    unittest.main()
