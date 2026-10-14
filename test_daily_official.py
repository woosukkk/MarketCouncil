import unittest
from unittest.mock import Mock
from desktop.daily_official import run_once, crypt, failure_record

class DailyTests(unittest.TestCase):
    def test_completed_never_prepares_or_spends(self):
        prepare=Mock(); analyze=Mock()
        self.assertEqual(run_once({"day":"2026-10-12","status":"completed"},"2026-10-12",prepare,analyze,Mock(),Mock()),"skipped")
        prepare.assert_not_called(); analyze.assert_not_called()
    def test_failure_blocks_automatic_paid_retry(self):
        state={}; analyze=Mock(side_effect=RuntimeError("failure"))
        with self.assertRaises(RuntimeError): run_once(state,"2026-10-12",Mock(),analyze,Mock(),Mock())
        self.assertEqual(state["status"],"analysis_failed")
        run_once(state,"2026-10-12",Mock(),analyze,Mock(),Mock())
        self.assertEqual(analyze.call_count,1)
    def test_failed_run_checks_existing_publication_without_spending(self):
        from desktop.daily_official import AlreadyPublished
        analyze=Mock(); prepare=Mock(side_effect=AlreadyPublished())
        with self.assertRaises(AlreadyPublished):run_once({"day":"2026-10-14","status":"analysis_failed"},"2026-10-14",prepare,analyze,Mock(),Mock())
        prepare.assert_called_once();analyze.assert_not_called()
    def test_resumed_analysis_has_two_attempt_daily_cap(self):
        state={"day":"2026-10-14","status":"analysis_failed","analysis_attempts":1};analyze=Mock(side_effect=RuntimeError())
        with self.assertRaises(RuntimeError):run_once(state,"2026-10-14",Mock(),analyze,Mock(),Mock(),resume=True)
        self.assertEqual(state["analysis_attempts"],2)
        self.assertEqual(run_once(state,"2026-10-14",Mock(),analyze,Mock(),Mock(),resume=True),"skipped")
        self.assertEqual(analyze.call_count,1)
    def test_upload_failure_reuses_saved_analysis(self):
        state={}; analyze=Mock(return_value="saved.json"); publish=Mock(side_effect=[RuntimeError("network"),None])
        with self.assertRaises(RuntimeError):run_once(state,"2026-10-12",Mock(),analyze,publish,Mock())
        self.assertEqual(state["status"],"pending_upload")
        self.assertEqual(run_once(state,"2026-10-12",Mock(),analyze,publish,Mock()),"completed")
        self.assertEqual(analyze.call_count,1)
    def test_permission_failure_never_analyzes(self):
        analyze=Mock()
        with self.assertRaises(RuntimeError):run_once({},"2026-10-12",Mock(side_effect=RuntimeError()),analyze,Mock(),Mock())
        analyze.assert_not_called()
    def test_failure_record_excludes_exception_content(self):
        import json
        report = failure_record("account", RuntimeError("private-token-and-key"))
        self.assertEqual(report["stage"], "account")
        self.assertNotIn("private", json.dumps(report))
    def test_wrapped_error_metadata_only(self):
        import json
        try:
            try: raise ValueError("private prompt")
            except ValueError as inner: raise RuntimeError("private token") from inner
        except RuntimeError as outer: report=failure_record("analysis",outer)
        self.assertEqual([x["type"] for x in report["causes"]],["RuntimeError","ValueError"])
        self.assertTrue(report["causes"][1]["locations"])
        self.assertNotIn("private",json.dumps(report))
    def test_windows_encryption_roundtrip(self):
        encrypted=crypt(b"test-credential")
        self.assertNotIn(b"test-credential",encrypted)
        self.assertEqual(crypt(encrypted,True),b"test-credential")

if __name__=="__main__":unittest.main()
