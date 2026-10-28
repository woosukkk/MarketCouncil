import {test} from 'node:test';
import assert from 'node:assert/strict';
import {measurementReport,monitoringSummary,metricText,reportTab,costText} from './adminData.js';

const base={schema_version:1,kind:'monitoring',id:'11111111-1111-4111-8111-111111111111',recorded_at:'2026-10-10T00:00:00Z',label:'삼성전자',scope:'analysis',status:'success',metrics:{duration_ms:10,cpu_ms:5}};
const clone=value=>structuredClone(value);
const usage=()=>({request_count:2,error_count:1,usage_known_calls:1,usage_missing_calls:1,input_tokens:100,output_tokens:20,cached_input_tokens:null,reasoning_tokens:null,estimated_cost_usd:.000056,cost_status:'partial',coverage:'observed_responses_only',sdk_retries_included:false,tool_costs_included:false,model:'gpt-5-mini',pricing:{model:'gpt-5-mini',currency:'USD',as_of:'2026-10-27',source:'openai_api_pricing',input_per_million:.25,cached_input_per_million:.025,output_per_million:2}});
const supportLabels=['supported','contradicted','insufficient_evidence'];
function quality(){
 const metrics={duration_ms:2,case_count:2,reviewed_count:1,compared_count:1,prediction_count:2,semantic_accuracy:1,review_coverage:.5,numeric_review_count:1,identity_invalid_count:1,future_source_count:0};
 for(const gold of supportLabels)for(const predicted of supportLabels)metrics['confusion_'+gold+'_'+predicted]=Number(gold==='supported'&&predicted==='supported');
 return {...base,kind:'rag',scope:'answer_quality',label:'Claim-evidence support',version:'1',dataset_hash:'a'.repeat(64),settings:{case_count:2,dataset_kind:'real',annotation_origin:'mixed',prediction_origin:'model',semantic_status:'evaluated',predictions_hash:'b'.repeat(64)},metrics,cases:[
  {case_id:'C-000001',input_hash:'c'.repeat(64),gold_origin:'human',prediction_origin:'model',gold_label:'supported',prediction_label:'supported',correct:1,numeric_review:true,identity_invalid:true,future_source:false},
  {case_id:'C-000002',input_hash:'d'.repeat(64),gold_origin:'unreviewed',prediction_origin:'model',gold_label:null,prediction_label:'contradicted',correct:null,numeric_review:false,identity_invalid:false,future_source:false}
 ]};
}

test('measurement import strips secrets, raw text and unsupported fields',()=>{
 const clean=measurementReport({...base,OPENAI_API_KEY:'secret',prompt:'private',environment:{os:'Windows',email:'private'},metrics:{...base.metrics,private:123}});
 assert.equal(clean.metrics.duration_ms,10);
 assert.equal(JSON.stringify(clean).includes('private'),false);
 assert.equal(JSON.stringify(clean).includes('secret'),false);
});
test('invalid metrics and fake incomplete benchmark records are rejected',()=>{
 assert.throws(()=>measurementReport({...base,metrics:{duration_ms:-1}}));
 assert.throws(()=>measurementReport({...base,metrics:{duration_ms:Infinity}}));
 assert.throws(()=>measurementReport({...base,kind:'rag'}));
 assert.equal(metricText(undefined),'미측정');
 assert.equal(metricText(NaN),'미측정');
});
test('summary excludes HTTP probes and never fabricates rates for no samples',()=>{
 assert.equal(monitoringSummary([]).successRate,null);
 const result=monitoringSummary([base,{...base,status:'failed'},{...base,scope:'web_http'}]);
 assert.equal(result.count,2);
 assert.equal(result.successRate,.5);
});
test('monitoring imports bounded measured stages and observed usage only',()=>{
 const raw={...base,stages:[{name:'collect',duration_ms:8,status:'success',cached:false,prompt:'private'},{name:'bull_initial',duration_ms:0,status:'success',cached:true,error:'secret'}],stages_truncated:false,llm:{...usage(),response:'private',api_key:'secret'}};
 const original=clone(raw),clean=measurementReport(raw);
 assert.deepEqual(raw,original);
 assert.equal(clean.stages[1].cached,true);
 assert.equal(clean.llm.usage_missing_calls,1);
 assert.equal(clean.llm.cached_input_tokens,null);
 assert.equal(costText(clean.llm),'$0.000056');
 assert.equal(JSON.stringify(clean).includes('private'),false);
 assert.equal(JSON.stringify(clean).includes('secret'),false);
 assert.equal(measurementReport(base).llm,null);
 assert.equal(costText(measurementReport(base).llm),'미측정');
});
test('contradictory usage and malformed stages cannot become reported measurements',()=>{
 const mutations=[
  raw=>{raw.llm.usage_missing_calls=0},
  raw=>{raw.llm.cached_input_tokens=101},
  raw=>{raw.llm.reasoning_tokens=21},
  raw=>{raw.llm.cost_status='estimated'},
  raw=>{raw.llm.sdk_retries_included=true},
  raw=>{raw.llm.tool_costs_included=true},
  raw=>{raw.llm.estimated_cost_usd=-1},
  raw=>{raw.llm.pricing.as_of='2026-02-31'},
  raw=>{raw.llm.pricing.input_per_million=Infinity},
  raw=>{raw.stages[0].name='https://private.example'},
  raw=>{raw.stages[0].duration_ms=NaN},
  raw=>{raw.stages[0].cached='yes'},
  raw=>{raw.stages=Array.from({length:1001},()=>raw.stages[0])},
  raw=>{raw.stages_truncated='yes'}
 ];
 for(const mutate of mutations){
  const raw={...base,llm:usage(),stages:[{name:'collect',duration_ms:1,status:'success',cached:false}]};
  mutate(raw);
  assert.throws(()=>measurementReport(raw));
 }
});
test('no API observations or incomplete zero estimates remain unmeasured',()=>{
 const empty={request_count:0,error_count:0,usage_known_calls:0,usage_missing_calls:0,input_tokens:null,output_tokens:null,cached_input_tokens:null,reasoning_tokens:null,estimated_cost_usd:null,cost_status:'unavailable',coverage:'observed_responses_only',sdk_retries_included:false,tool_costs_included:false,model:null,pricing:null};
 assert.equal(costText(measurementReport({...base,llm:empty}).llm),'미측정');
 assert.throws(()=>measurementReport({...base,llm:{...empty,input_tokens:0}}));
 assert.throws(()=>measurementReport({...base,llm:{...empty,estimated_cost_usd:0}}));
 assert.equal(costText(measurementReport({...base,llm:{...usage(),estimated_cost_usd:0}}).llm),'미측정');
 const clean=measurementReport({...base,llm:{...usage(),model:'sk-private-value',estimated_cost_usd:null,cost_status:'unavailable'}});
 assert.equal(clean.llm.model,null);
});
test('quality and retrieval remain separate while private review text is removed',()=>{
 const raw=quality();
 raw.claim='private';
 raw.label='private';
 raw.version='private';
 raw.settings.model='private';
 raw.settings.prompt='private';
 raw.environment={os:'private'};
 raw.cases[0].quote='private';
 raw.cases[0].source_url='https://private.example';
 const clean=measurementReport(raw);
 assert.equal(clean.metrics.semantic_accuracy,1);
 assert.equal(clean.metrics.review_coverage,.5);
 assert.equal(clean.settings.predictions_hash,'b'.repeat(64));
 assert.equal(JSON.stringify(clean).includes('private'),false);
 assert.equal(reportTab(clean),'quality');
 assert.equal(reportTab({...clean,scope:'retrieval'}),'rag');
 assert.equal(reportTab(base),'monitoring');
});
test('quality counts and confusion matrix must match independent labeled cases',()=>{
 const mutations=[
  raw=>{raw.metrics.reviewed_count=2},
  raw=>{raw.metrics.compared_count=2},
  raw=>{raw.metrics.semantic_accuracy=.5},
  raw=>{raw.metrics.semantic_accuracy=1.0000000001},
  raw=>{raw.metrics.review_coverage=1},
  raw=>{raw.metrics.review_coverage=1.0000000001},
  raw=>{raw.metrics.confusion_supported_contradicted=1},
  raw=>{raw.metrics.future_source_count=3},
  raw=>{raw.cases[0].correct=true},
  raw=>{raw.cases[1].case_id=raw.cases[0].case_id},
  raw=>{raw.cases[1].input_hash=raw.cases[0].input_hash},
  raw=>{raw.cases[1].prediction_origin='unreviewed'},
  raw=>{raw.settings.semantic_status='not_evaluated'},
  raw=>{raw.settings.dataset_kind='expert'},
  raw=>{raw.settings.annotation_origin='human'},
  raw=>{raw.settings.prediction_origin='human'},
  raw=>{raw.cases[0].gold_origin='unreviewed'},
  raw=>{raw.cases[0].numeric_review='yes'},
  raw=>{delete raw.cases[0].future_source},
  raw=>{raw.metrics.numeric_review_count=0},
  raw=>{raw.settings.case_count=3},
  raw=>{raw.cases[0].gold_label='certainly_true'}
 ];
 for(const mutate of mutations){const raw=quality();mutate(raw);assert.throws(()=>measurementReport(raw));}
 const overlapping=quality();
 for(const row of overlapping.cases){row.numeric_review=true;row.identity_invalid=true;row.future_source=true;}
 overlapping.metrics.numeric_review_count=2;overlapping.metrics.identity_invalid_count=2;overlapping.metrics.future_source_count=2;
 assert.equal(measurementReport(overlapping).metrics.future_source_count,2);
});
test('model agreement cannot masquerade as human semantic accuracy',()=>{
 const raw=quality();
 raw.settings.annotation_origin='model';
 raw.settings.semantic_status='not_evaluated';
 raw.settings.dataset_kind='synthetic';
 raw.metrics.reviewed_count=0;raw.metrics.compared_count=0;raw.metrics.semantic_accuracy=null;raw.metrics.review_coverage=0;
 for(const gold of supportLabels)for(const prediction of supportLabels)raw.metrics['confusion_'+gold+'_'+prediction]=0;
 raw.cases[0].gold_origin='model';raw.cases[0].correct=null;
 raw.cases[1].gold_origin='model';raw.cases[1].gold_label='contradicted';
 const clean=measurementReport(raw);
 assert.equal(clean.metrics.semantic_accuracy,null);
 assert.equal(clean.settings.dataset_kind,'synthetic');
 assert.equal(metricText(clean.metrics.semantic_accuracy,true),'미측정');
 raw.metrics.semantic_accuracy=1;
 assert.throws(()=>measurementReport(raw));
});

test('per-phase observed usage reconciles with totals without treating parallel time as wall time',()=>{
 const complete={request_count:1,error_count:0,usage_known_calls:1,usage_missing_calls:0,input_tokens:100,output_tokens:20,cached_input_tokens:40,reasoning_tokens:5,estimated_cost_usd:.000056,cost_status:'estimated',model:'gpt-5-mini'};
 const unknown={request_count:1,error_count:1,usage_known_calls:0,usage_missing_calls:1,input_tokens:null,output_tokens:null,cached_input_tokens:null,reasoning_tokens:null,estimated_cost_usd:null,cost_status:'unavailable',model:'gpt-5-mini'};
 const raw={...base,llm:{...usage(),by_phase:[{phase:'bull_initial',duration_ms:30,...complete,response:'private'},{phase:'bear_initial',duration_ms:10,...unknown,error:'secret'}]}};
 const clean=measurementReport(raw);
 assert.equal(clean.llm.by_phase.length,2);
 assert.equal(clean.llm.cached_input_tokens,null);
 assert.equal(clean.llm.by_phase[0].cached_input_tokens,40);
 assert.equal(clean.metrics.duration_ms,10);
 assert.equal(JSON.stringify(clean).includes('private'),false);
 assert.equal(JSON.stringify(clean).includes('secret'),false);
 for(const mutate of [
  report=>{report.llm.error_count=0},
  report=>{report.llm.by_phase[0].input_tokens=101},
  report=>{report.llm.by_phase[0].estimated_cost_usd=.1},
  report=>{report.llm.by_phase[1].phase='bull_initial'},
  report=>{report.llm.by_phase[0].phase='private_phase'},
  report=>{report.llm.by_phase=[]},
  report=>{report.llm.by_phase=Array.from({length:17},()=>report.llm.by_phase[0])}
 ]){
  const altered=clone(raw);mutate(altered);
  assert.throws(()=>measurementReport(altered));
 }
});
test('tiny observed costs never round down to a displayed zero',()=>{
 assert.equal(costText({...usage(),estimated_cost_usd:.00000025,cost_status:'estimated'}),'< $0.000001');
});

test('finite individual costs cannot overflow into an accepted phase total',()=>{
 const phase={request_count:1,error_count:0,usage_known_calls:1,usage_missing_calls:0,input_tokens:1,output_tokens:1,cached_input_tokens:0,reasoning_tokens:0,estimated_cost_usd:Number.MAX_VALUE,cost_status:'estimated',model:'gpt-5-mini',duration_ms:1};
 const raw={...base,llm:{...usage(),request_count:2,error_count:0,usage_known_calls:2,usage_missing_calls:0,input_tokens:2,output_tokens:2,cached_input_tokens:0,reasoning_tokens:0,estimated_cost_usd:Number.MAX_VALUE,cost_status:'estimated',by_phase:[{...phase,phase:'bull_initial'},{...phase,phase:'bear_initial'}]}};
 assert.throws(()=>measurementReport(raw));
});

test('unobserved calls cannot fabricate a priced partial cost',()=>{
 const unknown={...usage(),request_count:1,error_count:1,usage_known_calls:0,usage_missing_calls:1,input_tokens:null,output_tokens:null,cached_input_tokens:null,reasoning_tokens:null,estimated_cost_usd:.02,cost_status:'partial',pricing:null};
 assert.throws(()=>measurementReport({...base,llm:unknown}));
 assert.throws(()=>measurementReport({...base,llm:{...unknown,pricing:usage().pricing}}));
 const clean=measurementReport({...base,llm:{...unknown,estimated_cost_usd:null,cost_status:'unavailable'}});
 assert.equal(costText(clean.llm),'미측정');
 assert.equal(measurementReport({...base,llm:usage()}).llm.cost_status,'partial');
});
test('priced observations require matching declared rates and coherent complete estimates',()=>{
 const complete={...usage(),request_count:1,error_count:0,usage_known_calls:1,usage_missing_calls:0,cached_input_tokens:40,reasoning_tokens:5,cost_status:'estimated'};
 assert.equal(measurementReport({...base,llm:complete}).llm.estimated_cost_usd,.000056);
 for(const mutate of [
  raw=>{raw.pricing=null},
  raw=>{delete raw.pricing},
  raw=>{raw.model='gpt-4.1'},
  raw=>{raw.model='sk-private-value'},
  raw=>{raw.estimated_cost_usd=.02},
  raw=>{raw.cached_input_tokens=null},
  raw=>{raw.pricing.cached_input_per_million=raw.pricing.input_per_million+1},
  raw=>{raw.pricing.output_per_million=1000001}
 ]){
  const altered=clone(complete);mutate(altered);
  assert.throws(()=>measurementReport({...base,llm:altered}));
 }
 assert.throws(()=>measurementReport({...base,llm:{...usage(),pricing:null}}));
 assert.throws(()=>measurementReport({...base,llm:{...usage(),model:'gpt-4.1'}}));
 const mixed=measurementReport({...base,llm:{...usage(),model:null}});
 assert.equal(mixed.llm.cost_status,'partial');
});
