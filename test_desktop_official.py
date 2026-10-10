import unittest
from unittest.mock import patch
from desktop.cloud import prepare_official, publish_official

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
        with patch('desktop.cloud.request',side_effect=[True,[],'2026-10-10',True,[],'2026-10-10']) as api,patch('desktop.cloud.upload_result') as upload:
            self.assertEqual(publish_official(DATA,SESSION),'2026-10-10')
            publish_official(DATA,SESSION)
            self.assertEqual(upload.call_args_list[0].args[2],upload.call_args_list[1].args[2])
            self.assertEqual(api.call_args.args[0],'/rest/v1/rpc/select_daily_official')
            self.assertEqual(api.call_args.args[2],'token')

    def test_expired_session_is_refreshed_before_permission_check(self):
        with patch('desktop.cloud.request',side_effect=[SESSION,True,[]]) as api:
            self.assertEqual(prepare_official({**SESSION,'refresh_token':'refresh'}),SESSION)
            self.assertEqual(api.call_args_list[0].args[0],'/auth/v1/token?grant_type=refresh_token')

if __name__=='__main__':unittest.main()
