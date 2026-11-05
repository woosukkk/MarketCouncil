import profiles from './companyProfiles.json' with {type:'json'};

const types=['annual','interim','earnings','report'];
const fields=['schema_version','policy_version','company_name','ticker','as_of_date','status','missing','counts','corpus_hash','documents'];
const documentFields=['document_id','document_type','published_at','report_date','content_hash','source_url'];
const hash=/^[a-f0-9]{64}$/;
const object=value=>value!==null&&typeof value==='object'&&!Array.isArray(value);
const compare=(a,b)=>a<b?-1:a>b?1:0;
const fail=()=>{throw Error('근거 준비 보고서의 기업·원문 식별 정보와 판정을 확인하세요.');};
const batchFail=()=>{throw Error('6개 기업의 근거 준비 현황 JSON을 선택하세요.');};
const name=value=>typeof value==='string'?value.replace(/\s/g,'').toLowerCase():'';
const keys=(value,required,optional=[])=>object(value)&&required.every(key=>Object.hasOwn(value,key))&&Object.keys(value).every(key=>required.includes(key)||optional.includes(key));

function profileFor(company,ticker){
 const profile=typeof ticker==='string'&&profiles.find(row=>row.ticker===ticker.trim().toUpperCase());
 if(!profile||typeof company!=='string'||!profile.aliases.some(alias=>name(alias)===name(company)))fail();
 return profile;
}
function day(value){
 if(typeof value!=='string'||value.length!==10||value.startsWith('0000-')||!/^\d{4}-\d{2}-\d{2}$/.test(value))fail();
 const number=Date.parse(value+'T00:00:00Z');
 if(!Number.isFinite(number)||new Date(number).toISOString().slice(0,10)!==value)fail();
 return number/86400000;
}
const kstDay=timestamp=>new Date(timestamp+9*3600000).toISOString().slice(0,10);
function officialUrl(profile,value){
 if(typeof value!=='string'||value.length>2000||/[\u0000-\u0020\u007f]/.test(value))fail();
 const rawPath=value.match(/^https:\/\/[^/?#]+([^?#]*)/i)?.[1]||'';
 let url,path;
 try{url=new URL(value);path=decodeURIComponent(rawPath);}catch{fail();}
 if(url.protocol!=='https:'||url.username||url.password||url.port||path.includes('\\')||path.split('/').some(part=>part==='.'||part==='..'))fail();
 const host=url.hostname.toLowerCase();
 let normalized;
 if(host==='dart.fss.or.kr'){
  const receipts=url.searchParams.getAll('rcpNo');
  if(profile.market!=='kr'||rawPath!=='/dsaf001/main.do'||receipts.length!==1||!/^\d{14}$/.test(receipts[0]))fail();
  normalized='https://'+host+rawPath+'?rcpNo='+receipts[0];
 }else if(host==='www.sec.gov'){
  const filing=path.match(/^\/Archives\/edgar\/data\/(\d+)\/(\d{18})\/[^/]+$/);
  if(profile.market!=='us'||!filing||Number(filing[1])!==Number(profile.sec_cik))fail();
  normalized='https://'+host+rawPath;
 }else{
  const sources=[...profile.ir_sources,...(profile.filing_sources||[])].filter(source=>source.host===host);
  if(!sources.some(source=>source.path_prefixes.some(prefix=>path.toLowerCase().startsWith(prefix.toLowerCase()))))fail();
  if(sources.some(source=>source.is_document!==true&&path.replace(/\/+$/,'').toLowerCase()===decodeURIComponent(new URL(source.url).pathname).replace(/\/+$/,'').toLowerCase()))fail();
  normalized='https://'+host+rawPath;
 }
 if(normalized!==value)fail();
 return value;
}
function requirements(documents,cutoff){
 const recent=(row,periodDays,publishedDays)=>cutoff-day(row.report_date)<=periodDays&&cutoff-day(row.published_at)<=publishedDays;
 const annual=documents.filter(row=>row.document_type==='annual'&&recent(row,550,550));
 const interim=documents.some(row=>row.document_type==='interim'&&recent(row,200,200));
 const recentAnnual=annual.some(row=>recent(row,200,120));
 const earnings=documents.some(row=>row.document_type==='earnings'&&recent(row,200,200));
 return [['annual_missing',annual.length>0],['recent_financial_missing',interim||recentAnnual],['earnings_missing',earnings]].filter(([,good])=>!good).map(([code])=>code);
}
function structure(report,company,ticker,{todayOnly=false}={}){
 const profile=profileFor(company,ticker);
 if(!keys(report,fields,['selection_reason'])||report.schema_version!==1||report.policy_version!=='primary-v1'||profileFor(report.company_name,report.ticker).ticker!==profile.ticker)fail();
 if(Object.hasOwn(report,'selection_reason')&&!['new_official_event','rotation'].includes(report.selection_reason))fail();
 const cutoff=day(report.as_of_date);
 if(todayOnly&&report.as_of_date!==kstDay(Date.now()))throw Error('공식 게시 전에 오늘의 근거 준비 상태를 다시 확인하세요.');
 if(!Array.isArray(report.documents)||report.documents.length>200)fail();
 const hashes=new Set(),ids=new Set(),urls=new Set();
 const documents=report.documents.map(row=>{
  if((!keys(row,documentFields,['date_basis'])||(Object.hasOwn(row,'date_basis')&&row.date_basis!=='first_retrieved'))||!types.includes(row.document_type)||typeof row.content_hash!=='string'||row.content_hash.length!==64||!hash.test(row.content_hash)||hashes.has(row.content_hash)||typeof row.document_id!=='string'||row.document_id.length<1||row.document_id.length>160||/[^A-Za-z0-9_.:-]/.test(row.document_id)||!/^[A-Za-z0-9]/.test(row.document_id)||ids.has(row.document_id))fail();
  const published=day(row.published_at),period=day(row.report_date);
  if(period>published||published>cutoff||cutoff-published>550)fail();
  officialUrl(profile,row.source_url);
  if(urls.has(row.source_url))fail();
  if(new URL(row.source_url).hostname==='dart.fss.or.kr'){
   const receipt=new URL(row.source_url).searchParams.get('rcpNo');
   if(day(receipt.slice(0,4)+'-'+receipt.slice(4,6)+'-'+receipt.slice(6,8))!==published)fail();
  }
  hashes.add(row.content_hash);ids.add(row.document_id);urls.add(row.source_url);
  return {...Object.fromEntries(documentFields.map(key=>[key,row[key]])),...(row.date_basis?{date_basis:row.date_basis}:{})};
 });
 const counts=Object.fromEntries(types.map(type=>[type,documents.filter(row=>row.document_type===type).length]));
 if(!keys(report.counts,types)||types.some(type=>!Number.isSafeInteger(report.counts[type])||report.counts[type]!==counts[type]))fail();
 const missing=requirements(documents,cutoff);
 if(!Array.isArray(report.missing)||JSON.stringify(report.missing)!==JSON.stringify(missing)||report.status!==(missing.length?'insufficient':'ready')||typeof report.corpus_hash!=='string'||report.corpus_hash.length!==64||!hash.test(report.corpus_hash))fail();
 return {schema_version:1,policy_version:'primary-v1',company_name:profile.company_name,ticker:profile.ticker,as_of_date:report.as_of_date,status:report.status,missing,counts,corpus_hash:report.corpus_hash,documents,...(report.selection_reason?{selection_reason:report.selection_reason}:{})};
}
export function canonicalReadinessJson(value){
 if(Array.isArray(value))return '['+value.map(canonicalReadinessJson).join(',')+']';
 if(object(value))return '{'+Object.keys(value).sort(compare).map(key=>JSON.stringify(key)+':'+canonicalReadinessJson(value[key])).join(',')+'}';
 return JSON.stringify(value);
}
export function sanitizeReadinessReport(report,company,ticker){
 return structure(report,company,ticker);
}
export async function validateReadinessReport(report,company,ticker,options={}){
 const clean=structure(report,company,ticker,options);
 const corpus={policy_version:'primary-v1',company_name:clean.company_name,ticker:clean.ticker,documents:[...clean.documents].sort((a,b)=>compare(a.document_id,b.document_id)||compare(a.content_hash,b.content_hash))};
 if(!globalThis.crypto?.subtle)fail();
 const bytes=await globalThis.crypto.subtle.digest('SHA-256',new TextEncoder().encode(canonicalReadinessJson(corpus)));
 const digest=Array.from(new Uint8Array(bytes),byte=>byte.toString(16).padStart(2,'0')).join('');
 if(digest!==clean.corpus_hash)fail();
 return clean;
}
export const collectionFailureCodes=['collection_failed','manifest_missing','invalid_manifest','download_failed','source_unavailable','date_unavailable','body_unavailable','issuer_mismatch','cache_invalid'];
export function readinessBatchStructure(raw){
 if(!object(raw)||raw.schema_version!==1||raw.kind!=='monitoring'||raw.scope!=='evidence_readiness'||raw.version!=='primary-v1'||raw.status!=='success'||raw.label!=='Company evidence readiness'||typeof raw.id!=='string'||!/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(raw.id)||typeof raw.recorded_at!=='string'||!/^\d{4}-\d{2}-\d{2}T.*(?:Z|[+-]\d{2}:\d{2})$/.test(raw.recorded_at)||!Number.isFinite(Date.parse(raw.recorded_at))||!object(raw.metrics)||typeof raw.metrics.duration_ms!=='number'||!Number.isFinite(raw.metrics.duration_ms)||raw.metrics.duration_ms<0||raw.settings?.case_count!==6||!Array.isArray(raw.companies)||raw.companies.length!==6)batchFail();
 day(raw.recorded_at.slice(0,10));
 const companies=raw.companies.map(report=>sanitizeReadinessReport(report,report?.company_name,report?.ticker));
 if(new Set(companies.map(report=>report.ticker)).size!==6||new Set(companies.map(report=>report.as_of_date)).size!==1||companies.some(report=>report.as_of_date>kstDay(Date.parse(raw.recorded_at))))batchFail();
 const failures=raw.collection_failures??[];
 if(!Array.isArray(failures)||failures.length>100)batchFail();
 const collection_failures=failures.map(row=>{
  if(!object(row)||typeof row.ticker!=='string'||!profiles.some(profile=>profile.ticker===row.ticker))batchFail();
  return {ticker:row.ticker,code:collectionFailureCodes.includes(row.code)?row.code:'collection_failed'};
 });
 return {schema_version:1,kind:'monitoring',scope:'evidence_readiness',id:raw.id,recorded_at:new Date(raw.recorded_at).toISOString(),label:'Company evidence readiness',version:'primary-v1',status:'success',metrics:{duration_ms:raw.metrics.duration_ms},settings:{case_count:6},environment:{},cases:[],companies,collection_failures};
}
export async function validateReadinessBatch(raw){
 const clean=readinessBatchStructure(raw);
 clean.companies=await Promise.all(clean.companies.map(report=>validateReadinessReport(report,report.company_name,report.ticker)));
 return clean;
}
