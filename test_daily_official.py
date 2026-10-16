import unittest
from unittest.mock import Mock, patch
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
    def test_old_database_stops_daily_run_before_services_or_paid_analysis(self):
        import tempfile
        from pathlib import Path
        from desktop.daily_official import run
        from desktop.cloud import CloudAPIError
        session={'user':{'id':'owner'},'access_token':'token','refresh_token':'rotated'}
        with tempfile.TemporaryDirectory() as folder,patch('desktop.daily_official.DATA',Path(folder)),patch('desktop.daily_official.credentials',return_value={'refresh_token':'old'}),patch('desktop.daily_official.save_credentials'),patch('desktop.daily_official.source_version',return_value='test'),patch('desktop.daily_official.save_failure') as failure,patch('desktop.daily_official.notify') as notification,patch('desktop.cloud.request',side_effect=[session,True,[],CloudAPIError(404)]),patch('app.local_services.ensure_local_services') as services:
            self.assertEqual(run(),1)
            services.assert_not_called()
            self.assertEqual(failure.call_args.args[0],'account')
            self.assertIn('DB 마이그레이션',str(failure.call_args.args[1]))
            self.assertIn('DB 마이그레이션',notification.call_args.args[0])
            self.assertIn('OfficialSchemaRequired',failure_record('account',failure.call_args.args[1])['error_type'])

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
    def test_credit_balance_code_survives_wrapping_without_secret_content(self) -> None:
        import json,tempfile
        from pathlib import Path
        inner=RuntimeError('private provider message')
        inner.status_code=429
        inner.code='credit_balance_exhausted'
        inner.body={'error':{'message':'private API key and prompt'}}
        outer=RuntimeError('private authorization token')
        outer.__cause__=inner
        with tempfile.TemporaryDirectory() as folder,patch('desktop.daily_official.DATA',Path(folder)):
            report=failure_record('analysis',outer)
        self.assertEqual(report['causes'][1]['api_code'],'credit_balance_exhausted')
        self.assertEqual(report['causes'][1]['http_status'],429)
        self.assertNotIn('private',json.dumps(report))
        self.assertNotIn('body',report['causes'][1])

    def test_failure_history_preserves_legacy_and_separates_runs(self):
        import json,tempfile
        from pathlib import Path
        from desktop.daily_official import save_failure
        with tempfile.TemporaryDirectory() as folder,patch('desktop.daily_official.DATA',Path(folder)),patch('desktop.daily_official.source_version',return_value='abc123'):
            (Path(folder)/'last-error.json').write_text('{"stage":"original"}',encoding='utf-8')
            save_failure('analysis',RuntimeError('private token'),'run1')
            save_failure('publish',RuntimeError('private prompt'),'run2')
            files=list((Path(folder)/'errors').glob('*.json'))
            self.assertEqual(len(files),3)
            self.assertEqual(json.loads((Path(folder)/'errors/legacy-first-error.json').read_text())['stage'],'original')
            latest=json.loads((Path(folder)/'last-error.json').read_text())
            self.assertEqual(latest['run_id'],'run2');self.assertEqual(latest['source_version'],'abc123')
            self.assertNotIn('private token',''.join(p.read_text() for p in files))
            self.assertTrue(latest['recorded_at'])
    def test_windows_encryption_roundtrip(self):
        encrypted=crypt(b"test-credential")
        self.assertNotIn(b"test-credential",encrypted)
        self.assertEqual(crypt(encrypted,True),b"test-credential")

if __name__=="__main__":unittest.main()
