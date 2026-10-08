import {test} from 'node:test';
import assert from 'node:assert/strict';
import {safeUrl,issueStatus,evidenceCount,filterSessions} from './data.js';
test('evidence links reject executable and local URLs',()=>{
  for(const u of ['javascript:alert(1)','data:text/html,test','file:///C:/secret','/private']) assert.equal(safeUrl(u),null);
  assert.equal(safeUrl('https://example.com/report#page=3'),'https://example.com/report#page=3');
});
test('old sessions remain readable and editorial status takes precedence',()=>{
  assert.equal(issueStatus({},'a'),'UNKNOWN'); assert.equal(evidenceCount({}),0);
  assert.equal(issueStatus({navigation:{issues:[{issue_id:'a',status:'RESOLVED'}]},issue_statuses:[{issue_id:'a',status:'OPEN'}]},'a'),'RESOLVED');
  assert.equal(filterSessions([{company_name:'삼성전자',created_at:'2026-09-27',summary:''}],'  삼성 ').length,1);
});
