import os
import unittest
from unittest.mock import patch, MagicMock
from desktop.cloud import login_link, upload_result

class DesktopTests(unittest.TestCase):
    def test_login_rejects_other_projects_and_non_auth_urls(self) -> None:
        for link in ['http://snembdnkylggbxtxfqyz.supabase.co/auth/v1/verify?token=x&type=magiclink', 'https://evil.example/auth/v1/verify?token=x&type=magiclink']:
            with self.assertRaises(ValueError): login_link(link)

    def test_private_upload_strips_context_and_never_sets_visibility(self) -> None:
        payload={'company_name':'Example','rounds':[{'bull_response':{'issues':[{'evidence':[{'exact_quote':'Used','context_text':'Full document'}]}]}}]}
        session={'user':{'id':'owner'},'access_token':'user-token'}
        with patch('desktop.cloud.request', side_effect=[[],[{'id':'saved'}]]) as api:
            upload_result(payload,session,'11111111-1111-4111-8111-111111111111')
            row=api.call_args.args[1]
            self.assertNotIn('visibility',row)
            self.assertNotIn('context_text',row['payload']['rounds'][0]['bull_response']['issues'][0]['evidence'][0])
            self.assertEqual(api.call_args.args[2],'user-token')
        with patch('desktop.cloud.request',return_value=[{'id':'saved'}]) as api:
            upload_result(payload,session,'11111111-1111-4111-8111-111111111111')
            self.assertEqual(api.call_count,1)

    def test_empty_library_does_not_download_model(self) -> None:
        from rag.retriever import ReportRetriever
        with patch('rag.retriever.get_chroma_client') as client:
            client.return_value.get_or_create_collection.return_value.count.return_value=0
            retriever=ReportRetriever()
            self.assertEqual(retriever.search('Example',company_name='Example'),[])
            self.assertIsNone(retriever.model)

    def test_company_filter_is_combined_with_document_type(self) -> None:
        from rag.retriever import ReportRetriever
        with patch('rag.retriever.get_chroma_client') as client:
            collection=client.return_value.get_or_create_collection.return_value
            collection.count.return_value=1
            collection.query.return_value={'documents':[[]],'metadatas':[[]],'distances':[[]]}
            retriever=ReportRetriever();retriever.model=MagicMock()
            retriever.search('Example',company_name='Example',source_types={'regulatory_filing'})
            self.assertEqual(collection.query.call_args.kwargs['where'],{'$and':[{'source_type':'regulatory_filing'},{'company':'Example'}]})

    def test_explicit_ticker_selects_other_company(self) -> None:
        from tools.financial_data import get_financial_data
        with patch.dict(os.environ,{'MARKETCOUNCIL_TICKER':'AAPL'}),patch('tools.financial_data.yf.Ticker',side_effect=RuntimeError('stop before network')) as ticker:
            with self.assertRaises(RuntimeError):get_financial_data('Apple')
            ticker.assert_called_once_with('AAPL')
        with patch.dict(os.environ,{'MARKETCOUNCIL_TICKER':'bad/path'}):
            with self.assertRaises(ValueError):get_financial_data('Apple')

if __name__=='__main__': unittest.main()
