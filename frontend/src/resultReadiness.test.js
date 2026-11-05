import {test} from 'node:test';
import assert from 'node:assert/strict';
import fixture from './evidenceReadiness.fixture.json' with {type:'json'};
import {prepareResult,uploadResult} from './resultUpload.js';

const clone=value=>structuredClone(value);
const error=/분석 결과 형식이 올바르지 않아 열 수 없습니다/;
const reportFor=(ticker,status='ready')=>clone((status==='ready'?fixture.reports:fixture.empty_reports).find(report=>report.ticker===ticker));
const resultFor=(report,location='root')=>({company_name:report.company_name,created_at:'2026-11-03T04:00:00Z',rounds:[],financial_data:{ticker:report.ticker,...(location==='financial'?{readiness_report:report}:{})},...(location==='root'?{readiness_report:report}:{})});
function clientStub(){
 const inserts=[],reads=[];
 const client={from:table=>{
  assert.equal(table,'discussions');
  return {select:()=>({eq:(_field,id)=>({maybeSingle:async()=>{reads.push(id);return {data:inserts.some(row=>row.id===id)?{id}:null,error:null};}})}),insert:async row=>{inserts.push(row);return {error:null};}};
 }};
 return {client,inserts,reads};
}

test('result importer preserves valid historical ready and insufficient reports at either supported location',()=>{
 for(const status of ['ready','insufficient'])for(const location of ['root','financial']){
  const report=reportFor('AAPL',status),raw=resultFor(report,location),before=clone(raw);
  const payload=prepareResult('\uFEFF'+JSON.stringify(raw));
  assert.deepEqual(location==='root'?payload.readiness_report:payload.financial_data.readiness_report,report);
  assert.deepEqual(raw,before);
  assert.equal(payload.company_name,'Apple Inc.');
  assert.equal(payload.financial_data.ticker,'AAPL');
 }
});

test('result importer rejects mismatched company pairs and malformed or raw readiness fields',()=>{
 const mutations=[
  raw=>{raw.company_name='Microsoft Corporation';},
  raw=>{raw.financial_data.ticker='MSFT';},
  raw=>{raw.readiness_report=[];},
  raw=>{raw.readiness_report.status='insufficient';},
  raw=>{raw.readiness_report.counts.annual=99;},
  raw=>{raw.readiness_report.company_name='Microsoft Corporation';},
  raw=>{raw.readiness_report.raw_text='Original private document';},
  raw=>{raw.readiness_report.local_path='C:\\private\\report.txt';},
  raw=>{raw.readiness_report.api_key='secret';},
  raw=>{raw.readiness_report.documents[0].content='Original private document';},
  raw=>{raw.readiness_report.documents[0].source_path='C:\\private';},
 ];
 for(const mutate of mutations){
  const raw=resultFor(reportFor('AAPL'));mutate(raw);
  assert.throws(()=>prepareResult(JSON.stringify(raw)),error);
 }
 for(const field of ['content','local_path','secret']){
  const raw=resultFor(reportFor('AAPL'),'financial');
  raw.financial_data.readiness_report[field]='private';
  assert.throws(()=>prepareResult(JSON.stringify(raw)),error);
 }
});

test('private result upload validates ready and insufficient evidence without granting publication',async()=>{
 const {client,inserts}=clientStub();
 for(const status of ['ready','insufficient'])for(const location of ['root','financial']){
  const text=JSON.stringify(resultFor(reportFor('AAPL',status),location));
  assert.deepEqual(await uploadResult(client,{user:{id:'owner'}},text),{duplicate:false});
  assert.deepEqual(await uploadResult(client,{user:{id:'owner'}},text),{duplicate:true});
 }
 assert.equal(inserts.length,4);
 for(const row of inserts){
  assert.equal(row.user_id,'owner');
  assert.equal(row.ticker,'AAPL');
  for(const field of ['visibility','share_token','official_date','is_official'])assert.equal(Object.hasOwn(row,field),false);
  const report=row.payload.readiness_report||row.payload.financial_data.readiness_report;
  assert.ok(['ready','insufficient'].includes(report.status));
 }
});

test('upload rejects a forged corpus SHA before any Supabase request at either location',async()=>{
 for(const status of ['ready','insufficient'])for(const location of ['root','financial']){
  const report=reportFor('AAPL',status);
  report.corpus_hash='0'.repeat(64);
  const raw=resultFor(report,location),text=JSON.stringify(raw);
  // Synchronous import checks safe structure; asynchronous upload authenticates metadata SHA.
  assert.doesNotThrow(()=>prepareResult(text));
  const {client,inserts,reads}=clientStub();
  await assert.rejects(()=>uploadResult(client,{user:{id:'owner'}},text),error);
  assert.equal(reads.length,0);assert.equal(inserts.length,0);
 }
});

test('upload checks both report locations when a file contains both snapshots',async()=>{
 const raw=resultFor(reportFor('AAPL'));
 raw.financial_data.readiness_report=reportFor('AAPL');
 raw.financial_data.readiness_report.documents[0].content_hash='1'.repeat(64);
 const {client,reads}=clientStub();
 await assert.rejects(()=>uploadResult(client,{user:{id:'owner'}},JSON.stringify(raw)),error);
 assert.equal(reads.length,0);
});
