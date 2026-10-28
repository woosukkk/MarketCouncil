const numericKeys=['performance_score','fcp_ms','lcp_ms','tbt_ms','cls','speed_index_ms','duration_ms','cpu_ms','recall','precision','mrr','hit','median_ms','p95_ms','mixed_company','unknown_company','future_sources','request_count','error_count'];
const apiPhases=new Set(['source_collection','bull_initial','bear_initial','regime_reasons','shorts_debate_topics','video_summary','debate_navigation','debate_agenda','debate_review','debate_summary','bull_debate_turn','bear_debate_turn','report_source_collection','bull_web_search','bear_web_search','unclassified']);
const supportLabels=['supported','contradicted','insufficient_evidence'];
const origins=['human','model','unreviewed'];
const stageNames=new Set(['collect','financial_data','valuation','filing_search','bull_report_search','bear_report_search','report_context','web_collection','source_classification','evidence_resolution','web_context','history','regime','regime_reasons','bull_initial','bear_initial','sentiment','shorts','video_topics','video_summary','create_agenda','bull_turn','bear_turn','moderator_review','summarize','navigation']);
const text=(value,limit=120)=>typeof value==='string'?value.slice(0,limit):'';
const hash=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
const object=value=>!!value&&typeof value==='object'&&!Array.isArray(value);
const integer=value=>Number.isSafeInteger(value)&&value>=0;
const number=value=>typeof value==='number'&&Number.isFinite(value)&&value>=0;
const equal=(a,b)=>Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a-b)<=Math.max(1,Math.abs(a),Math.abs(b))*1e-9;
const fail=()=>{throw Error('성능 기록의 수치와 평가 조건을 확인하세요.');};
const model=value=>typeof value==='string'&&/^(?:gpt-|chatgpt-|o[1-9])[a-z0-9][a-z0-9._-]{0,100}$/.test(value)?value:null;

function stages(raw){
 if(raw===undefined)return [];
 if(!Array.isArray(raw)||raw.length>1000)fail();
 return raw.map(row=>{
  if(!object(row)||!stageNames.has(row.name)||!number(row.duration_ms)||!['success','failed'].includes(row.status)||typeof row.cached!=='boolean')fail();
  return {name:row.name,duration_ms:row.duration_ms,status:row.status,cached:row.cached};
 });
}
function usageValues(raw){
 if(!object(raw))fail();
 const clean={};
 for(const key of ['request_count','error_count','usage_known_calls','usage_missing_calls']){
  if(!integer(raw[key]))fail();
  clean[key]=raw[key];
 }
 if(clean.usage_known_calls+clean.usage_missing_calls!==clean.request_count||clean.error_count>clean.request_count)fail();
 for(const key of ['input_tokens','output_tokens','cached_input_tokens','reasoning_tokens']){
  if(raw[key]!==null&&!integer(raw[key]))fail();
  clean[key]=raw[key];
 }
 if(clean.usage_known_calls===0&&['input_tokens','output_tokens','cached_input_tokens','reasoning_tokens'].some(key=>clean[key]!==null))fail();
 if(clean.usage_known_calls>0&&(clean.input_tokens===null||clean.output_tokens===null))fail();
 if(clean.usage_missing_calls>0&&(clean.cached_input_tokens!==null||clean.reasoning_tokens!==null))fail();
 if(clean.cached_input_tokens!==null&&clean.input_tokens!==null&&clean.cached_input_tokens>clean.input_tokens)fail();
 if(clean.reasoning_tokens!==null&&clean.output_tokens!==null&&clean.reasoning_tokens>clean.output_tokens)fail();
 if(!['estimated','partial','unavailable'].includes(raw.cost_status)||raw.estimated_cost_usd!==null&&!number(raw.estimated_cost_usd))fail();
 if(raw.cost_status==='unavailable'&&raw.estimated_cost_usd!==null||raw.cost_status!=='unavailable'&&raw.estimated_cost_usd===null)fail();
 if(raw.cost_status==='estimated'&&clean.usage_missing_calls>0)fail();
 if(clean.usage_known_calls===0&&(raw.estimated_cost_usd!==null||raw.cost_status!=='unavailable'))fail();
 if(raw.estimated_cost_usd!==null&&raw.model!==null&&model(raw.model)===null)fail();
 return {...clean,estimated_cost_usd:raw.estimated_cost_usd,cost_status:raw.cost_status,model:model(raw.model)};
}
function pricedUsage(row,pricing){
 if(row.estimated_cost_usd===null)return;
 if(!pricing||row.model!==null&&row.model!==pricing.model)fail();
 if(row.cost_status==='estimated'){
  if(row.model===null||row.cached_input_tokens===null)fail();
  const expected=((row.input_tokens-row.cached_input_tokens)*pricing.input_per_million+row.cached_input_tokens*pricing.cached_input_per_million+row.output_tokens*pricing.output_per_million)/1e6;
  if(!equal(row.estimated_cost_usd,expected))fail();
 }
}
function llmUsage(raw){
 if(raw===undefined||raw===null)return null;
 const clean=usageValues(raw);
 if(raw.coverage!=='observed_responses_only'||raw.sdk_retries_included!==false||raw.tool_costs_included!==false)fail();
 Object.assign(clean,{coverage:raw.coverage,sdk_retries_included:false,tool_costs_included:false,pricing:null,by_phase:[]});
 if(raw.pricing!==undefined&&raw.pricing!==null){
  const pricing=raw.pricing;
  if(!object(pricing)||!model(pricing.model)||pricing.currency!=='USD'||!['openai_api_pricing','manual'].includes(pricing.source)||typeof pricing.as_of!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(pricing.as_of)||!Number.isFinite(Date.parse(pricing.as_of+'T00:00:00Z'))||new Date(pricing.as_of+'T00:00:00Z').toISOString().slice(0,10)!==pricing.as_of)fail();
  clean.pricing={model:pricing.model,currency:'USD',as_of:pricing.as_of,source:pricing.source};
  for(const key of ['input_per_million','cached_input_per_million','output_per_million']){
   if(!number(pricing[key])||pricing[key]>1e6)fail();
   clean.pricing[key]=pricing[key];
  }
  if(clean.pricing.cached_input_per_million>clean.pricing.input_per_million)fail();
 }
 pricedUsage(clean,clean.pricing);
 if(raw.by_phase!==undefined){
  if(!Array.isArray(raw.by_phase)||raw.by_phase.length>16)fail();
  const names=new Set();
  clean.by_phase=raw.by_phase.map(row=>{
   if(!object(row)||!apiPhases.has(row.phase)||names.has(row.phase)||!number(row.duration_ms))fail();
   names.add(row.phase);
   const phase={phase:row.phase,duration_ms:row.duration_ms,...usageValues(row)};
   pricedUsage(phase,clean.pricing);
   return phase;
  });
  for(const key of ['request_count','error_count','usage_known_calls','usage_missing_calls'])if(clean.by_phase.reduce((sum,row)=>sum+row[key],0)!==clean[key])fail();
  for(const key of ['input_tokens','output_tokens','cached_input_tokens','reasoning_tokens']){
   const rows=clean.by_phase;
   const present=rows.filter(row=>row[key]!==null);
   const sum=rows.length&&present.length&&(key==='input_tokens'||key==='output_tokens'||present.length===rows.length)?present.reduce((total,row)=>total+row[key],0):null;
   if(clean[key]!==sum)fail();
  }
  const priced=clean.by_phase.filter(row=>row.estimated_cost_usd!==null);
  const sum=priced.length?priced.reduce((total,row)=>total+row.estimated_cost_usd,0):null;
  if(clean.estimated_cost_usd!==sum&&(sum===null||clean.estimated_cost_usd===null||!equal(clean.estimated_cost_usd,sum)))fail();
 }
 return clean;
}
function quality(raw,settings){
 if(!['real','synthetic'].includes(raw.settings?.dataset_kind)||![...origins,'mixed'].includes(raw.settings?.annotation_origin)||!origins.includes(raw.settings?.prediction_origin)||!['evaluated','not_evaluated'].includes(raw.settings?.semantic_status))fail();
 for(const key of ['dataset_kind','annotation_origin','prediction_origin','semantic_status'])settings[key]=raw.settings[key];
 if(raw.settings.predictions_hash!==undefined){if(!hash(raw.settings.predictions_hash))fail();settings.predictions_hash=raw.settings.predictions_hash;}
 if(!Array.isArray(raw.cases)||raw.cases.length<1||raw.cases.length>1000||raw.cases.length!==settings.case_count)fail();
 const ids=new Set(),hashes=new Set();
 const cases=raw.cases.map(row=>{
  if(!object(row)||typeof row.case_id!=='string'||!/^C-\d{6}$/.test(row.case_id)||!hash(row.input_hash)||ids.has(row.case_id)||hashes.has(row.input_hash)||!origins.includes(row.gold_origin)||!origins.includes(row.prediction_origin))fail();
  ids.add(row.case_id);hashes.add(row.input_hash);
  for(const key of ['gold_label','prediction_label'])if(row[key]!==null&&!supportLabels.includes(row[key]))fail();
  if(row.prediction_origin!==settings.prediction_origin||row.prediction_origin==='unreviewed'&&row.prediction_label!==null||row.gold_origin==='unreviewed'&&row.gold_label!==null)fail();
  for(const key of ['numeric_review','identity_invalid','future_source'])if(typeof row[key]!=='boolean')fail();
  const compared=row.gold_origin==='human'&&row.gold_label!==null&&row.prediction_label!==null;
  const correct=compared?Number(row.gold_label===row.prediction_label):null;
  if(row.correct!==correct)fail();
  return {case_id:row.case_id,input_hash:row.input_hash,gold_origin:row.gold_origin,prediction_origin:row.prediction_origin,gold_label:row.gold_label,prediction_label:row.prediction_label,correct,numeric_review:row.numeric_review,identity_invalid:row.identity_invalid,future_source:row.future_source};
 });
 const declaredOrigins=new Set(cases.map(row=>row.gold_origin));
 if(settings.annotation_origin!==(declaredOrigins.size===1?[...declaredOrigins][0]:'mixed'))fail();
 const metrics={};
 for(const key of ['case_count','reviewed_count','compared_count','prediction_count','numeric_review_count','identity_invalid_count','future_source_count']){
  if(!integer(raw.metrics?.[key])||raw.metrics[key]>cases.length)fail();
  metrics[key]=raw.metrics[key];
 }
 for(const [key,flag] of [['numeric_review_count','numeric_review'],['identity_invalid_count','identity_invalid'],['future_source_count','future_source']])if(metrics[key]!==cases.filter(row=>row[flag]).length)fail();
 const reviewed=cases.filter(row=>row.gold_origin==='human'&&row.gold_label!==null).length;
 const compared=cases.filter(row=>row.correct!==null);
 const predictions=cases.filter(row=>row.prediction_label!==null).length;
 if(metrics.case_count!==cases.length||metrics.reviewed_count!==reviewed||metrics.compared_count!==compared.length||metrics.prediction_count!==predictions)fail();
 const accuracy=compared.length?compared.reduce((sum,row)=>sum+row.correct,0)/compared.length:null;
 if(raw.metrics.semantic_accuracy!==null&&(!number(raw.metrics.semantic_accuracy)||raw.metrics.semantic_accuracy>1))fail();
 if(raw.metrics.semantic_accuracy!==accuracy&&(accuracy===null||!number(raw.metrics.semantic_accuracy)||!equal(raw.metrics.semantic_accuracy,accuracy)))fail();
 if(!number(raw.metrics.review_coverage)||raw.metrics.review_coverage>1||!equal(raw.metrics.review_coverage,reviewed/cases.length))fail();
 if(raw.settings.semantic_status!==(compared.length?'evaluated':'not_evaluated'))fail();
 Object.assign(metrics,{semantic_accuracy:accuracy,review_coverage:raw.metrics.review_coverage});
 if(!number(raw.metrics.duration_ms))fail();
 metrics.duration_ms=raw.metrics.duration_ms;
 for(const gold of supportLabels)for(const prediction of supportLabels){
  const key='confusion_'+gold+'_'+prediction;
  const expected=compared.filter(row=>row.gold_label===gold&&row.prediction_label===prediction).length;
  if(!integer(raw.metrics[key])||raw.metrics[key]!==expected)fail();
  metrics[key]=expected;
 }
 return {metrics,cases};
}
export function measurementReport(raw){
 if(!object(raw)||raw.schema_version!==1||!['monitoring','rag'].includes(raw.kind)||!/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(raw.id||'')||!Number.isFinite(Date.parse(raw.recorded_at))||!text(raw.label)||!['success','failed'].includes(raw.status))throw Error('지원하는 성능 기록 JSON을 선택하세요.');
 const metrics={};
 for(const key of numericKeys){const value=raw.metrics?.[key];if(value===undefined||value===null)continue;if(!number(value)||(['performance_score','recall','precision','mrr','hit'].includes(key)&&value>1))fail();metrics[key]=value;}
 if(raw.kind==='monitoring'&&metrics.duration_ms===undefined)throw Error('측정 시간이 없는 기록입니다.');
 const settings={};
 for(const key of ['top_k','repeats','case_count','corpus_count']){const n=raw.settings?.[key];if(n!==undefined){if(!Number.isSafeInteger(n)||n<1)fail();settings[key]=n;}}
 const isQuality=raw.kind==='rag'&&raw.scope==='answer_quality';
 if(raw.kind==='rag'&&(!hash(raw.dataset_hash)||(!isQuality&&(!['recall','precision','mrr','median_ms','p95_ms'].every(k=>metrics[k]!==undefined)||!settings.case_count||!settings.top_k||!settings.repeats))))throw Error('정답 기반 평가 수치와 데이터셋 정보가 필요합니다.');
 if(!isQuality)for(const key of ['model','timing','corpus_hash','form_factor','lighthouse_version'])if(raw.settings?.[key])settings[key]=text(raw.settings[key]);
 const environment={};
 if(!isQuality)for(const key of ['os','python'])if(raw.environment?.[key])environment[key]=text(raw.environment[key]);
 if(!isQuality&&Number.isSafeInteger(raw.environment?.cpu_count)&&raw.environment.cpu_count>0)environment.cpu_count=raw.environment.cpu_count;
 let cases=[];
 if(isQuality){
  if(!settings.case_count)fail();
  const result=quality(raw,settings);
  for(const key of Object.keys(metrics))delete metrics[key];
  Object.assign(metrics,result.metrics);
  cases=result.cases;
 }else{
  cases=(Array.isArray(raw.cases)?raw.cases:[]).slice(0,1000).map(row=>{
   if(!object(row))fail();
   return {case_id:text(row.case_id),...Object.fromEntries(['repeat','duration_ms','recall','precision','mrr','hit','mixed_company','unknown_company','future_sources','retrieved_count'].filter(key=>number(row[key])).map(key=>[key,row[key]]))};
  });
 }
 const clean={schema_version:1,kind:raw.kind,id:raw.id,recorded_at:new Date(raw.recorded_at).toISOString(),label:isQuality?'Claim-evidence support':text(raw.label),version:isQuality?'1':text(raw.version)||'미지정',scope:text(raw.scope)||'미지정',status:raw.status,metrics,settings,environment,...(raw.kind==='rag'?{dataset_hash:raw.dataset_hash}:{}),cases};
 if(raw.kind==='monitoring'){
  if(raw.stages_truncated!==undefined&&typeof raw.stages_truncated!=='boolean')fail();
  Object.assign(clean,{stages:stages(raw.stages),stages_truncated:raw.stages_truncated??false,llm:llmUsage(raw.llm)});
 }
 return clean;
}
export const metricText=(n,percent=false)=>typeof n==='number'&&Number.isFinite(n)?percent?(n*100).toFixed(1)+'%':n.toLocaleString('ko-KR',{maximumFractionDigits:1}):'미측정';
export const reportTab=report=>report.kind==='monitoring'?'monitoring':report.scope==='answer_quality'?'quality':'rag';
export function costText(llm){
 if(!llm||llm.estimated_cost_usd===null||llm.cost_status==='unavailable'||(llm.cost_status==='partial'&&llm.estimated_cost_usd===0))return '미측정';
 if(llm.estimated_cost_usd>0&&llm.estimated_cost_usd<0.000001)return '< $0.000001';
 return '$'+llm.estimated_cost_usd.toLocaleString('en-US',{minimumFractionDigits:4,maximumFractionDigits:6});
}
export function monitoringSummary(rows){
 const runs=rows.filter(row=>row.scope==='analysis');
 return {count:runs.length,successRate:runs.length?runs.filter(row=>row.status==='success').length/runs.length:null,averageMs:runs.length?runs.reduce((sum,row)=>sum+row.metrics.duration_ms,0)/runs.length:null};
}
