import unittest
from unittest.mock import Mock
from tools.evidence_catalog import EvidenceCatalog
from tools.citation_quality import assess_issue_evidence
from agents.analysis_debate_agent import AnalysisDebateAgent


class QuoteCandidateTests(unittest.TestCase):
    def entry(self, content: str) -> dict:
        return EvidenceCatalog._with_quotes({'source_id':'S1','content':content,'published_at':'20261016'})

    def test_long_navigation_does_not_hide_body(self) -> None:
        content='\n'.join('[Logo](https://example.com/nav)' for _ in range(100))+'\n\n2025년 매출은 100억원이고 영업이익은 12억원이다.'
        entry=self.entry(content)
        self.assertTrue(entry['quotes'])
        self.assertIn('매출은 100억원',entry['quotes'][0]['text'])
        self.assertNotIn('Logo',entry['quotes'][0]['text'])

    def test_short_table_values_keep_labels_and_exact_source_context(self) -> None:
        content='주요사항보고서\n취득 예정 주식 수 (주)\n53,285,968\n취득 예정 금액 (원)\n14,999,999,992,000\n취득 방법: 장내매수'
        entry=self.entry(content)
        self.assertEqual(len(entry['quotes']),1)
        self.assertIn('53,285,968',entry['quotes'][0]['text'])
        self.assertIn('취득 예정 주식 수 (주)',entry['quotes'][0]['text'])
        self.assertEqual(entry['quotes'][0]['text'],content)

    def test_navigation_only_is_empty_and_duplicate_excerpts_are_removed(self) -> None:
        self.assertEqual(self.entry('[Logo](https://example.com)\n[Skip Navigation](#content)')['quotes'],[])
        repeated='실제 매출은 100억원이며 사업 계획을 확인한다.'
        entry=self.entry(repeated+'\n[Logo](https://example.com)\n'+repeated)
        self.assertEqual([q['text'] for q in entry['quotes']],[repeated])

    def test_bounded_excerpts_are_substrings_and_do_not_merge_across_navigation(self) -> None:
        content='\n'.join(f'{i}번째 기업의 사업 실적과 반대 근거를 확인하는 설명 문장이다. '*30 for i in range(40))
        entry=self.entry(content)
        self.assertEqual(len(entry['quotes']),16)
        for q in entry['quotes']:
            self.assertLessEqual(len(q['text']),500)
            self.assertIn(q['text'],content)
        content='매출 100억원이라는 첫 번째 원문이다.\n[Logo](https://example.com)\n영업이익 12억원이라는 두 번째 원문이다.'
        entry=self.entry(content)
        self.assertEqual(len(entry['quotes']),2)
        for q in entry['quotes']:self.assertNotIn('Logo',q['text'])

    def test_snippet_status_is_preserved_in_model_catalog(self) -> None:
        catalog=EvidenceCatalog.build({},[],[{'content':'매출은 100억원이며 이는 검색 요약에서만 확인했다.', 'extraction_method':'search_snippet_fallback','body_extraction_status':'snippet_only'}])
        item=EvidenceCatalog.for_prompt(catalog)[1]
        self.assertEqual(item['body_extraction_status'],'snippet_only')
        self.assertEqual(item['extraction_method'],'search_snippet_fallback')

    def test_krw_conversion_is_provided_without_model_rounding(self) -> None:
        entry=EvidenceCatalog._financial_entry({'financial_facts':{'financial_currency':'KRW'},'derived_metrics':{'normalized_fcf':11265213750000}})
        quote=next(q['text'] for q in entry['quotes'] if '(normalized_fcf)=' in q['text'])
        self.assertIn('11265213750000 KRW',quote)
        self.assertIn('11.26521375조원',quote)

    def test_navigation_catalog_quote_warns_and_is_removed_from_usable_evidence(self) -> None:
        quote='[Skip Navigation](https://example.com/#content)'
        catalog=[{'source_id':'S1','content':quote,'published_at':'2026-10-16','quotes':[{'quote_id':'Q1','text':quote}]}]
        issue={'issue_id':'I1','claim':'매출이 개선됐다','evidence':[{'source_id':'S1','quote_id':'Q1'}]}
        quality=assess_issue_evidence(issue,catalog,'2026-10-16')
        self.assertEqual(quality['identity_status'],'matched')
        self.assertEqual(quality['semantic_status'],'not_evaluated')
        self.assertIn('non_evidentiary_quote',quality['warnings'])
        response=AnalysisDebateAgent._validate_citations({'issues':[issue]},catalog,'2026-10-16')
        self.assertEqual(response['issues'][0]['evidence'],[])
        self.assertTrue(response['issues'][0]['citation_errors'])

    def test_quality_review_blocks_resolved_status_without_asserting_falsehood(self) -> None:
        response={'issues':[{'issue_id':'I1','citation_quality':{'identity_status':'matched','warnings':['number_not_in_quotes'],'semantic_status':'not_evaluated'}}]}
        review={'issue_reviews':[{'issue_id':'I1','status':'RESOLVED','assessment':'모델의 기존 평가','question_for_bull':'질문','question_for_bear':'질문'}],'missing_evidence':[]}
        AnalysisDebateAgent._apply_quality_limits(review,response)
        issue=review['issue_reviews'][0]
        self.assertEqual(issue['status'],'UNKNOWN')
        self.assertEqual(issue['model_status'],'RESOLVED')
        self.assertEqual(issue['assessment'],'모델의 기존 평가')
        self.assertTrue(review['missing_evidence'])
        self.assertNotIn('falsehood',issue)

    def test_heuristic_age_warning_alone_does_not_force_unknown(self) -> None:
        response={'issues':[{'issue_id':'I1','citation_quality':{'identity_status':'matched','warnings':['stale_forecast']}}]}
        review={'issue_reviews':[{'issue_id':'I1','status':'CONTESTED'}]}
        AnalysisDebateAgent._apply_quality_limits(review,response)
        self.assertEqual(review['issue_reviews'][0]['status'],'CONTESTED')


if __name__=='__main__':unittest.main()
