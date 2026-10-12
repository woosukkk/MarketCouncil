import unittest
from unittest.mock import Mock
from desktop.daily_official import run_once, crypt

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
    def test_windows_encryption_roundtrip(self):
        encrypted=crypt(b"test-credential")
        self.assertNotIn(b"test-credential",encrypted)
        self.assertEqual(crypt(encrypted,True),b"test-credential")

if __name__=="__main__":unittest.main()
