import {test} from 'node:test';
import assert from 'node:assert/strict';
import fixture from './evidenceReadiness.fixture.json' with {type:'json'};
import profiles from '../src/companyProfiles.json' with {type:'json'};
import {sanitizeReadinessReport,validateReadinessReport,validateReadinessBatch,readinessBatchStructure,canonicalReadinessJson} from '../src/evidenceReadiness.js';
import {measurementReport,prepareMeasurementReport,reportTab,monitoringSummary} from '../src/adminData.js';

const clone=value=>structuredClone(value);
const batch=companies=>({schema_version:1,kind:'monitoring',scope:'evidence_readiness',id:'11111111-1111-4111-8111-111111111111',recorded_at:'2026-11-03T01:00:00Z',label:'Company evidence readiness',version:'primary-v1',status:'success',metrics:{duration_ms:1250},settings:{case_count:6},companies:clone(companies||fixture.reports)});

test('Python-produced reports verify with canonical UTF-8 SHA-256 for all six companies',async()=>{
 assert.equal(fixture.origin,'synthetic_test_only');
 assert.equal(fixture.reports.length,6);
 for(const report of fixture.reports){
  const before=clone(report),clean=await validateReadinessReport(report,report.company_name,report.ticker);
  assert.deepEqual(clean,report);
  assert.deepEqual(report,before);
  assert.equal(clean.status,'ready');
 }
 assert.equal(canonicalReadinessJson({z:['한글',1],a:{y:2,b:1}}),'{"a":{"b":1,"y":2},"z":["한글",1]}');
});

test('insufficient Python corpora remain valid evidence states without invented quality scores',async()=>{
 for(const report of fixture.empty_reports){
  const clean=await validateReadinessReport(report,report.company_name,report.ticker);
  assert.equal(clean.status,'insufficient');
  assert.deepEqual(clean.counts,{annual:0,interim:0,earnings:0,report:0});
  assert.equal(clean.missing.length,3);
 }
 const clean=await prepareMeasurementReport(batch(fixture.empty_reports));
 assert.equal(clean.status,'success','Collection completion does not claim all companies are ready');
 assert.equal(clean.companies.filter(report=>report.status==='ready').length,0);
 assert.deepEqual(Object.keys(clean.metrics),['duration_ms']);
 assert.equal(reportTab(clean),'readiness');
 assert.equal(monitoringSummary([clean]).count,0);
});

test('today-only publication rejects historical snapshots but allows historical viewing',async()=>{
 const report=clone(fixture.reports.find(row=>row.ticker==='AAPL'));
 const originalNow=Date.now;
 try{
  Date.now=()=>Date.parse('2026-11-03T04:00:00Z');
  await validateReadinessReport(report,'Apple','AAPL',{todayOnly:true});
  report.as_of_date='2026-11-02';
  await validateReadinessReport(report,'Apple','AAPL');
  await assert.rejects(()=>validateReadinessReport(report,'Apple','AAPL',{todayOnly:true}),/오늘의 근거 준비/);
 }finally{Date.now=originalNow;}
});

test('altered issuer, counts, missing roles, dates, source URL and hash cannot become ready',async()=>{
 const initial=fixture.reports.find(row=>row.ticker==='AAPL');
 const mutations=[
  raw=>{raw.ticker='MSFT'},raw=>{raw.company_name='Microsoft Corporation'},
  raw=>{raw.schema_version=true},raw=>{raw.policy_version='made-up'},
  raw=>{raw.counts.annual=true},raw=>{raw.counts.annual=100},
  raw=>{raw.missing=['annual_missing']},raw=>{raw.status='insufficient'},
  raw=>{raw.corpus_hash='0'.repeat(64)},raw=>{raw.as_of_date='2026-02-31'},
  raw=>{raw.documents[0].published_at='2026-11-04'},
  raw=>{raw.documents[0].report_date='2026-11-03'},
  raw=>{raw.documents[0].source_url='https://www.sec.gov.evil.example/filing'},
  raw=>{raw.documents[0].source_url=raw.documents[0].source_url.replace('/320193/','/789019/')},
  raw=>{raw.documents[0].document_id='C:\\Users\\private\\file.pdf'},
  raw=>{raw.documents[0].content_hash='bad'},raw=>{raw.documents.push(clone(raw.documents[0]))},
  raw=>{raw.documents[1].content_hash=raw.documents[0].content_hash},
  raw=>{raw.documents[1].document_id=raw.documents[0].document_id},
  raw=>{raw.documents[1].source_url=raw.documents[0].source_url},
  raw=>{raw.documents[2].source_url='https://investor.apple.com/investor-relations/default.aspx'},
  raw=>{raw.documents[2].source_url='https://www.apple.com/shop/results'},
  raw=>{raw.documents[0].source_url+='?token=secret'},
  raw=>{raw.raw_text='private'},raw=>{raw.documents[0].content='private'},
 ];
 for(const mutate of mutations){
  const raw=clone(initial);mutate(raw);
  await assert.rejects(()=>validateReadinessReport(raw,'Apple','AAPL'));
 }
 const dart=clone(fixture.reports.find(row=>row.ticker==='005930.KS'));
 dart.documents[0].source_url='https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261029000001';
 await assert.rejects(()=>validateReadinessReport(dart,'삼성전자','005930.KS'));
});

test('a verified individual IR seed is not mistaken for an index',async()=>{
 const report=fixture.reports.find(row=>row.ticker==='AAPL');
 const profile=profiles.find(row=>row.ticker==='AAPL');
 const release=report.documents.find(row=>row.document_type==='earnings').source_url;
 profile.ir_sources.push({url:release,host:'www.apple.com',path_prefixes:['/newsroom/'],is_document:true});
 try{await validateReadinessReport(report,'Apple','AAPL');}
 finally{profile.ir_sources.pop();}
});

test('six-company readiness batches stay in the existing private monitoring kind',async()=>{
 const raw={...batch(),api_key:'secret',prompt:'private',environment:{path:'private'},metrics:{duration_ms:1250,private:3},collection_failures:[{ticker:'AAPL',code:'source_unavailable',raw_error:'private'},{ticker:'MSFT',code:'PRIVATE PROVIDER RESPONSE',path:'private'}]};
 const original=clone(raw),clean=await prepareMeasurementReport(raw);
 assert.deepEqual(raw,original);
 assert.equal(clean.kind,'monitoring');
 assert.equal(clean.scope,'evidence_readiness');
 assert.equal(clean.settings.case_count,6);
 assert.equal(clean.companies.length,6);
 assert.deepEqual(clean.collection_failures,[{ticker:'AAPL',code:'source_unavailable'},{ticker:'MSFT',code:'collection_failed'}]);
 assert.equal(JSON.stringify(clean).includes('private'),false);
 assert.equal(JSON.stringify(clean).includes('secret'),false);
 assert.equal(reportTab(clean),'readiness');
 assert.deepEqual(measurementReport(clean),clean);
 const summary=monitoringSummary([clean,{scope:'analysis',status:'success',metrics:{duration_ms:10}}]);
 assert.equal(summary.count,1);assert.equal(summary.averageMs,10);
});

test('malformed, incomplete and hash-forged batches are rejected before admin storage',async()=>{
 const mutations=[
  raw=>{raw.kind='rag'},raw=>{raw.scope='analysis'},raw=>{raw.version='1'},
  raw=>{raw.status='failed'},raw=>{raw.label='private'},raw=>{raw.settings.case_count=5},
  raw=>{raw.companies.pop()},raw=>{raw.companies[1]=clone(raw.companies[0])},
  raw=>{raw.companies[0].as_of_date='2026-11-02'},
  raw=>{raw.recorded_at='2026-11-02T00:00:00Z'},raw=>{raw.recorded_at='2026-11-31T00:00:00Z'},
  raw=>{raw.metrics.duration_ms=-1},raw=>{raw.metrics.duration_ms=Infinity},
  raw=>{raw.collection_failures=[{ticker:'UNKNOWN',code:'source_unavailable'}]},
 ];
 for(const mutate of mutations){const raw=batch();mutate(raw);assert.throws(()=>readinessBatchStructure(raw));}
 const forged=batch();forged.companies[0].corpus_hash='0'.repeat(64);
 await assert.rejects(()=>validateReadinessBatch(forged));
 await assert.rejects(()=>prepareMeasurementReport(forged));
});


test('sync result sanitizer permits insufficient evidence but rejects raw text and local paths',()=>{
 const raw=clone(fixture.empty_reports.find(report=>report.ticker==='AAPL'));
 const clean=sanitizeReadinessReport(raw,'Apple','AAPL');
 assert.notEqual(clean,raw);
 assert.deepEqual(clean,raw);
 assert.equal(typeof clean.then,'undefined');
 for(const changes of [{raw_text:'private'},{local_path:'C:\\private'},{secret:'private'}]){
  assert.throws(()=>sanitizeReadinessReport({...raw,...changes},'Apple','AAPL'));
 }
 const document=clone(fixture.reports.find(report=>report.ticker==='AAPL'));
 document.documents[0].original_path='C:\\private';
 assert.throws(()=>sanitizeReadinessReport(document,'Apple','AAPL'));
});

test('readiness cannot be relabeled as an analysis performance measurement',async()=>{
 const raw={...batch(),scope:'analysis'};
 assert.throws(()=>measurementReport(raw));
 await assert.rejects(()=>prepareMeasurementReport(raw));
});

test('actual admin evidence view renders zero readiness without invented accuracy',async()=>{
 const [{createServer},{createElement},{renderToStaticMarkup},{fileURLToPath},{translate}]=await Promise.all([import('vite'),import('react'),import('react-dom/server'),import('node:url'),import('../src/language.js')]);
 const server=await createServer({root:fileURLToPath(new URL('../',import.meta.url)),envFile:false,configFile:false,logLevel:'silent',server:{middlewareMode:true,hmr:false}});
 try{
  const {EvidenceReadinessSummary}=await server.ssrLoadModule('/src/Admin.jsx');
  const {LanguageContext}=await server.ssrLoadModule('/src/Language.jsx');
  const report=await prepareMeasurementReport(batch(fixture.empty_reports));
  const html=renderToStaticMarkup(createElement(LanguageContext.Provider,{value:{locale:'en',t:(text,values)=>translate(text,'en',values),setLocale:()=>{}}},createElement(EvidenceReadinessSummary,{report})));
  assert.match(html,/Company evidence readiness/);
  assert.match(html,/<strong>0 \/ 6<\/strong>/);
  assert.match(html,/They are not semantic accuracy or RAG retrieval quality scores/);
  assert.match(html,/More evidence needed/);
  assert.doesNotMatch(html,/%/);
 }finally{await server.close();}
});


test('sync report boundary matches Python for end newlines, URL dot paths and year zero',()=>{
 const initial=fixture.reports.find(report=>report.ticker==='AAPL');
 for(const mutate of [
  raw=>{raw.documents[0].document_id+='\n'},
  raw=>{raw.documents[0].content_hash+='\n'},
  raw=>{raw.corpus_hash+='\n'},
  raw=>{raw.documents[0].source_url=raw.documents[0].source_url.replace('/320193/','/320193/../320193/')},
 ]){
  const raw=clone(initial);mutate(raw);
  assert.throws(()=>sanitizeReadinessReport(raw,'Apple','AAPL'));
 }
 const empty=clone(fixture.empty_reports.find(report=>report.ticker==='AAPL'));
 empty.as_of_date='0000-01-01';
 assert.throws(()=>sanitizeReadinessReport(empty,'Apple','AAPL'));
});
