import {test} from 'node:test';
import assert from 'node:assert/strict';
import {safeUrl,issueStatus,evidenceCount,filterSessions, usedSources, resultsUrl} from '../src/data.js';
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
  const {resultKey}=await import('../src/data.js');
  assert.equal(resultKey('0123456789abcdef-1111111111111111'),resultKey('0123456789abcdef-2222222222222222'));
  assert.equal(resultKey('0123456789abcdef'),'0123456789abcdef');
});

test('research filters search summaries and sort without changing source rows',async()=>{
 const {researchRows}=await import('../src/data.js');
 const rows=[{company_name:'삼성전자',analysis_date:'2026-01-01',summary:'반도체 수요'},{company_name:'삼성전자',analysis_date:'2026-02-01'},{company_name:'다른기업',analysis_date:'invalid'}];
 assert.equal(researchRows(rows,' 반도체 ')[0],rows[0]);
 assert.deepEqual(researchRows(rows,'','삼성전자').map(x=>x.analysis_date),['2026-02-01','2026-01-01']);
 assert.equal(researchRows(rows)[2],rows[2]);assert.equal(rows[0].analysis_date,'2026-01-01');
});

test('library includes only public official discussions and sorts with archive',async()=>{
 const {mergeLibrary}=await import('../src/data.js');
 const archive=[{id:'old',company_name:'삼성전자',created_at:'2026-10-08'}];
 const dates=[{discussion_id:'official',publication_date:'2026-10-13'},{discussion_id:'private',publication_date:'2026-10-12'}];
 const rows=[{id:'official',company_name:'삼성전자',analysis_date:'2026-10-13',visibility:'public',issues:[{title:'a'}]},{id:'private',visibility:'private'},{id:'community',visibility:'public'}];
 const result=mergeLibrary(archive,dates,rows);
 assert.deepEqual(result.map(x=>x.id),['official','old']);assert.equal(result[0].discussion,true);assert.equal(result[0].issue_count,1);
 assert.equal(mergeLibrary([{...archive[0],created_at:'2026-10-13'}],dates,rows).length,1);
 assert.equal(archive.length,1);assert.equal(mergeLibrary(archive,[],[])[0],archive[0]);
});


test('repeated official discussion uses the latest publication date in any query order',async()=>{
 const {mergeLibrary}=await import('../src/data.js');
 const dates=[{discussion_id:'same',publication_date:'2026-10-16'},{discussion_id:'same',publication_date:'2026-10-12'}];
 const rows=[{id:'same',company_name:'삼성전자',analysis_date:'2026-10-10',visibility:'public'}];
 for(const selections of [dates,[...dates].reverse()]){
  const result=mergeLibrary([],selections,rows);
  assert.equal(result.length,1);assert.equal(result[0].official_date,'2026-10-16');
 }
});


test('official badges require a matching public discussion',async()=>{
 const {publicOfficialSelections}=await import('../src/data.js');
 const selections=['public','private','shared','missing'].map(discussion_id=>({discussion_id,publication_date:'2026-10-16'}));
 const rows=[{id:'public',visibility:'public'},{id:'private',visibility:'private'},{id:'shared',visibility:'shared'}];
 assert.deepEqual(publicOfficialSelections(selections,rows),[selections[0]]);
 assert.deepEqual(publicOfficialSelections(selections,[]),[]);
 assert.equal(selections.length,4);
});

test('same-day research from five companies remains separate when merged and filtered',async()=>{
 const {mergeLibrary,researchRows}=await import('../src/data.js');
 const companies=[['SK하이닉스','000660.KS'],['현대차','005380.KS'],['NAVER','035420.KS'],['Apple Inc.','AAPL'],['Microsoft Corporation','MSFT']];
 const rows=companies.map(([company_name,ticker],index)=>({id:`official-${index}`,company_name,ticker,analysis_date:'2026-11-03T09:00:00',visibility:'public'}));
 const archive=rows.map(row=>({id:`archive-${row.id}`,company_name:row.company_name,ticker:row.ticker,created_at:row.analysis_date}));
 const dates=rows.map(row=>({discussion_id:row.id,publication_date:'2026-11-03'}));
 const before=JSON.stringify({rows,archive,dates});
 const merged=mergeLibrary(archive,dates,rows);
 assert.equal(merged.length,companies.length);
 assert.deepEqual(new Set(merged.map(row=>row.id)),new Set(rows.map(row=>row.id)));
 for(const [company_name,ticker] of companies){
  const own=merged.find(row=>row.company_name===company_name);
  assert.equal(own.ticker,ticker);
  assert.equal(own.official_date,'2026-11-03');
  assert.deepEqual(researchRows(merged,'',company_name),[own]);
  assert.deepEqual(researchRows(merged,ticker.toLowerCase()),[own]);
  assert.deepEqual(researchRows(merged,company_name.toLowerCase()),[own]);
  const other=companies.find(([name])=>name!==company_name)[0];
  assert.deepEqual(researchRows(merged,ticker,other),[]);
 }
 assert.equal(JSON.stringify({rows,archive,dates}),before);
});
