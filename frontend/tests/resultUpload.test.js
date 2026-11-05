import {test} from 'node:test';
import assert from 'node:assert/strict';
import {prepareResult,uploadResult} from '../src/resultUpload.js';

const result={company_name:'Example',created_at:'2026-10-10',rounds:[{bull_response:{issues:[{evidence:[{exact_quote:'Cited',source_url:'https://example.com',context_text:'Private full document',api_key:'secret'}]}]}}],api_key:'secret',source_documents:['raw']};
test('result upload excludes raw context and credentials',()=>{
 const payload=prepareResult(JSON.stringify(result));
 assert.equal(payload.rounds[0].bull_response.issues[0].evidence[0].exact_quote,'Cited');
 assert.ok(!JSON.stringify(payload).includes('Private full document'));
 assert.ok(!JSON.stringify(payload).includes('secret'));
 assert.ok(!('source_documents' in payload));
});
test('rejects malformed and oversized results',()=>{
 for(const input of ['bad','[]','{}',JSON.stringify({...result,rounds:null})])assert.throws(()=>prepareResult(input));
 assert.throws(()=>prepareResult(JSON.stringify({...result,bull_analysis:'x'.repeat(2000000)})));
});
test('same account and result reuse ID without changing visibility',async()=>{
 const inserts=[];
 const client={from:()=>({select:()=>({eq:(_key,id)=>({maybeSingle:async()=>({data:inserts.some(row=>row.id===id)?{id}:null})})}),insert:async row=>{inserts.push(row);return {error:null}}})};
 const session={user:{id:'owner'}};
 await uploadResult(client,session,JSON.stringify(result));
 assert.deepEqual(await uploadResult(client,session,JSON.stringify(result)),{duplicate:true});
 assert.equal(inserts.length,1);assert.equal(inserts[0].user_id,'owner');
 assert.ok(!('visibility' in inserts[0]));assert.ok(!('share_token' in inserts[0]));
 await uploadResult(client,{user:{id:'other'}},JSON.stringify(result));
 assert.notEqual(inserts[0].id,inserts[1].id);
 await assert.rejects(()=>uploadResult(client,null,JSON.stringify(result)));
});



test('result upload retains the analysis evidence cutoff date',()=>{
 const payload=prepareResult(JSON.stringify({...result,analysis_as_of:'2026-10-16'}));
 assert.equal(payload.analysis_as_of,'2026-10-16');
});

test('five companies uploaded on the same day keep separate private result identities',async()=>{
 const companies=[['SK하이닉스','000660.KS'],['현대차','005380.KS'],['NAVER','035420.KS'],['Apple Inc.','AAPL'],['Microsoft Corporation','MSFT']];
 const inserts=[];
 const client={from:table=>{
  assert.equal(table,'discussions');
  return {select:()=>({eq:(_key,id)=>({maybeSingle:async()=>({data:inserts.find(row=>row.id===id)||null})})}),insert:async row=>{inserts.push(row);return {error:null}}};
 }};
 const session={user:{id:'owner'}};
 for(const [company_name,ticker] of companies){
  const text=JSON.stringify({...result,company_name,financial_data:{ticker},created_at:'2026-11-03T09:00:00'});
  assert.deepEqual(await uploadResult(client,session,text),{duplicate:false});
  assert.deepEqual(await uploadResult(client,session,text),{duplicate:true});
 }
 assert.equal(inserts.length,companies.length);
 assert.equal(new Set(inserts.map(row=>row.id)).size,companies.length);
 for(const [index,[company_name,ticker]] of companies.entries()){
  const row=inserts[index];
  assert.equal(row.user_id,'owner');
  assert.equal(row.company_name,company_name);
  assert.equal(row.ticker,ticker);
  assert.equal(row.analysis_date,'2026-11-03T09:00:00');
  assert.equal(row.payload.company_name,company_name);
  assert.equal(row.payload.financial_data.ticker,ticker);
  assert.ok(!('visibility' in row));
  assert.ok(!('share_token' in row));
 }
});
