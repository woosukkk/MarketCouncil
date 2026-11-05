export const externalMetrics=['faithfulness','context_precision','context_recall','factual_correctness'];
const fields=['framework_version','dataset_name','dataset_version','evaluator_model','reference_origin','metric_config_hash'];
const token=value=>typeof value==='string'&&/^[A-Za-z0-9][A-Za-z0-9._:/ +@-]{0,119}$/.test(value);
const hash=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
const object=value=>value&&typeof value==='object'&&!Array.isArray(value);
const exact=(value,keys)=>object(value)&&Object.keys(value).length===keys.length&&keys.every(key=>Object.hasOwn(value,key));
export function externalEvaluation(raw){
 const fail=()=>{throw Error('외부 평가 기록의 형식·조건·사례별 점수를 확인하세요.');};
 if(!object(raw)||raw.schema_version!==1||raw.kind!=='rag'||raw.scope!=='external_rag'||raw.status!=='success'||!/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(raw.id||'')||!Number.isFinite(Date.parse(raw.recorded_at))||!/(Z|[+-]\d{2}:\d{2})$/.test(raw.recorded_at||'')||!hash(raw.dataset_hash))fail();
 if(!exact(raw.settings,fields)||!fields.every(key=>token(raw.settings[key]))||!['human','mixed','synthetic'].includes(raw.settings.reference_origin)||!hash(raw.settings.metric_config_hash))fail();
 if(!Array.isArray(raw.cases)||!raw.cases.length||raw.cases.length>1000)fail();
 const seen=new Set(),cases=raw.cases.map(row=>{
  if(!exact(row,['case_id',...externalMetrics])||!/^[a-f0-9]{16}$/.test(row.case_id||'')||seen.has(row.case_id))fail();
  seen.add(row.case_id);
  for(const key of externalMetrics)if(row[key]!==null&&(typeof row[key]!=='number'||!Number.isFinite(row[key])||row[key]<0||row[key]>1))fail();
  return {...row};
 });
 const metrics={case_count:cases.length};
 for(const key of externalMetrics){const values=cases.map(row=>row[key]).filter(value=>value!==null);metrics[key]=values.length?values.reduce((a,b)=>a+b,0)/values.length:null;metrics[key+'_count']=values.length;}
 if(!externalMetrics.some(key=>metrics[key+'_count'])||!exact(raw.metrics,Object.keys(metrics)))fail();
 for(const [key,value] of Object.entries(metrics))if(value===null?raw.metrics[key]!==null:typeof raw.metrics[key]!=='number'||!Number.isFinite(raw.metrics[key])||Math.abs(raw.metrics[key]-value)>1e-9)fail();
 return {schema_version:1,kind:'rag',scope:'external_rag',status:'success',id:raw.id,recorded_at:new Date(raw.recorded_at).toISOString(),label:'Ragas · imported results',version:raw.settings.framework_version,dataset_hash:raw.dataset_hash,settings:{...raw.settings},metrics,cases};
}
