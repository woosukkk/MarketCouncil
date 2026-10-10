import {test} from 'node:test';
import assert from 'node:assert/strict';
import {prepareResult,uploadResult} from './resultUpload.js';

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

