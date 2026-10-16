import unittest
from unittest.mock import patch, Mock
from desktop.cloud import prepare_official, publish_official, check_official_schema, CloudAPIError

SESSION={'user':{'id':'owner'},'access_token':'token'}
DATA={'company_name':'삼성전자','financial_data':{'ticker':'005930.KS'},'rounds':[]}

class OfficialTests(unittest.TestCase):
    def test_non_editor_and_existing_day_block(self):
        with patch('desktop.cloud.request',return_value=False) as api:
            with self.assertRaisesRegex(ValueError,'운영자'):prepare_official(SESSION)
            self.assertEqual(api.call_count,1)
        with patch('desktop.cloud.request',side_effect=[True,[{'discussion_id':'existing'}]]):
            with self.assertRaisesRegex(ValueError,'이미'):prepare_official(SESSION)

    def test_wrong_company_never_uploads(self):
        with patch('desktop.cloud.request') as api:
            with self.assertRaises(ValueError):publish_official({'company_name':'Apple'},SESSION)
            api.assert_not_called()

    def test_private_upload_precedes_official_selection_and_stable_id(self):
        with patch('desktop.cloud.request',side_effect=[True,[],CloudAPIError(400),'2026-10-10',True,[],CloudAPIError(400),'2026-10-10']) as api,patch('desktop.cloud.upload_result') as upload:
            self.assertEqual(publish_official(DATA,SESSION),'2026-10-10')
            publish_official(DATA,SESSION)
            self.assertEqual(upload.call_args_list[0].args[2],upload.call_args_list[1].args[2])
            self.assertEqual(api.call_args.args[0],'/rest/v1/rpc/select_daily_official')
            self.assertEqual(api.call_args.args[2],'token')

    def test_same_result_retry_is_allowed_without_replacing_another_selection(self):
        with patch('desktop.cloud.request',side_effect=[True,[{'discussion_id':'same'}],CloudAPIError(400)]) as api:
            self.assertEqual(prepare_official(SESSION,'same'),SESSION)
            self.assertIn('discussions!inner(visibility)',api.call_args_list[1].args[0])
            self.assertIn('discussions.visibility=eq.public',api.call_args_list[1].args[0])
        with patch('desktop.cloud.request',side_effect=[True,[{'discussion_id':'other'}]]):
            with self.assertRaisesRegex(ValueError,'이미'):prepare_official(SESSION,'same')

    def test_official_request_fixes_day_and_never_silently_replaces(self):
        with patch('desktop.cloud.official_day',return_value='2026-10-16'),patch('desktop.cloud.request',side_effect=[True,[],CloudAPIError(400),'2026-10-16']) as api,patch('desktop.cloud.upload_result'):
            publish_official(DATA,SESSION)
            self.assertEqual(api.call_args.args[1]['expected_day'],'2026-10-16')
            self.assertIs(api.call_args.args[1]['replace_existing'],False)

    def test_old_database_stops_before_paid_analysis(self):
        from desktop.daily_official import run_once
        analyze=Mock();persist=Mock()
        with patch('desktop.cloud.request',side_effect=[True,[],CloudAPIError(404)]):
            with self.assertRaisesRegex(RuntimeError,'DB 마이그레이션'):
                run_once({},'2026-10-16',lambda:prepare_official(SESSION),analyze,Mock(),persist)
        analyze.assert_not_called();persist.assert_not_called()

    def test_same_result_retry_also_checks_database_setup_before_upload(self):
        with patch('desktop.cloud.request',side_effect=[True,[],CloudAPIError(404)]),patch('desktop.cloud.upload_result') as upload:
            with self.assertRaisesRegex(RuntimeError,'DB 마이그레이션'):publish_official(DATA,SESSION)
            upload.assert_not_called()

    def test_same_existing_result_still_requires_new_rpc_support(self):
        with patch('desktop.cloud.request',side_effect=[True,[{'discussion_id':'same'}],CloudAPIError(404)]):
            with self.assertRaisesRegex(RuntimeError,'DB 마이그레이션'):prepare_official(SESSION,'same')

    def test_schema_probe_is_null_and_other_failures_are_not_accepted(self):
        with patch('desktop.cloud.request',side_effect=CloudAPIError(400)) as api:
            check_official_schema(SESSION,'2026-10-16')
            self.assertEqual(api.call_args.args[1],{'discussion':None,'expected_day':'2026-10-16','replace_existing':False})
        for status in (401,403,429,500):
            with self.subTest(status=status),patch('desktop.cloud.request',side_effect=CloudAPIError(status)):
                with self.assertRaises(CloudAPIError):check_official_schema(SESSION,'2026-10-16')
        with patch('desktop.cloud.request',return_value='unexpected success'):
            with self.assertRaisesRegex(RuntimeError,'안전하게'):check_official_schema(SESSION,'2026-10-16')

    def test_http_error_retains_status_without_private_provider_body(self):
        import io
        from urllib.error import HTTPError
        from desktop.cloud import request
        original=HTTPError('https://private.example/token',404,'private message',{},io.BytesIO(b'private body'))
        with patch('desktop.cloud.urlopen',side_effect=original):
            with self.assertRaises(CloudAPIError) as caught:request('/rest/v1/rpc/select_daily_official',{},'private token')
        error=caught.exception
        self.assertEqual(vars(error),{'status_code':404})
        self.assertNotIn('private',str(error))
        self.assertIsNone(error.__cause__)

    def test_expired_session_is_refreshed_before_permission_check(self):
        with patch('desktop.cloud.request',side_effect=[SESSION,True,[],CloudAPIError(400)]) as api:
            self.assertEqual(prepare_official({**SESSION,'refresh_token':'refresh'}),SESSION)
            self.assertEqual(api.call_args_list[0].args[0],'/auth/v1/token?grant_type=refresh_token')

if __name__=='__main__':unittest.main()
