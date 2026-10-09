import {test} from 'node:test';
import assert from 'node:assert/strict';
import {safeUrl,issueStatus,evidenceCount,filterSessions, usedSources, resultsUrl} from './data.js';
test('evidence links reject executable and local URLs',()=>{
  for(const u of ['javascript:alert(1)','data:text/html,test','file:///C:/secret','/private']) assert.equal(safeUrl(u),null);
  assert.equal(safeUrl('https://example.com/report#page=3'),'https://example.com/report#page=3');
});
test('old sessions remain readable and editorial status takes precedence',()=>{
  assert.equal(issueStatus({},'a'),'UNKNOWN'); assert.equal(evidenceCount({}),0);
  assert.equal(issueStatus({navigation:{issues:[{issue_id:'a',status:'RESOLVED'}]},issue_statuses:[{issue_id:'a',status:'OPEN'}]},'a'),'RESOLVED');
  assert.equal(filterSessions([{company_name:'삼성전자',created_at:'2026-09-27',summary:''}],'  삼성 ').length,1);
});

test('sources group repeated citations without merging different documents',()=>{
 const evidence=[{source_id:'a',exact_quote:'quote A',evidence_id:'E1'},{source_id:'b',exact_quote:'quote B',evidence_id:'E1'}];
 const data={rounds:[{bull_response:{issues:[{issue_id:'I1',evidence}]},bear_response:{issues:[{issue_id:'I1',evidence:[evidence[0]]}]}}]};
 const sources=usedSources(data);
 assert.equal(sources.length,2); assert.equal(sources[0].uses.length,2); assert.deepEqual(sources[0].quotes,['quote A']);
 assert.deepEqual(usedSources({}),[]);
 assert.throws(()=>resultsUrl('../secret')); assert.equal(resultsUrl('index.json'),'/data/index.json');
});

 test('saved analysis identity survives content version updates', async () => {
  const {resultKey}=await import('./data.js');
  assert.equal(resultKey('0123456789abcdef-1111111111111111'),resultKey('0123456789abcdef-2222222222222222'));
  assert.equal(resultKey('0123456789abcdef'),'0123456789abcdef');
});
