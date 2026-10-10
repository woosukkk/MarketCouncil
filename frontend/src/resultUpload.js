const fields = ['company_name','created_at','financial_data','agenda','rounds','issue_statuses','moderator_summary','navigation','bull_analysis','bear_analysis'];
const evidenceFields = ['evidence_id','source_id','exact_quote','reason','verified','title','source_type','source_url','published_at','page_number','source_page_url'];
function compact(value) {
  if(Array.isArray(value)) return value.map(compact);
  if(value && typeof value==='object') return Object.fromEntries(Object.entries(value).filter(([key])=>!['context_text','source_documents','retrieved_chunks','api_key'].includes(key)).map(([key,child])=>[key,key==='evidence'&&Array.isArray(child)?child.map(item=>item&&typeof item==='object'?Object.fromEntries(evidenceFields.filter(f=>f in item).map(f=>[f,compact(item[f])])):item):compact(child)]));
  return value;
}
export function prepareResult(text) {
  let data;
  try {data=JSON.parse(text.replace(/^\uFEFF/,''));} catch {throw Error('분석 JSON 파일을 선택하세요. 파일 내용을 읽을 수 없습니다.');}
  if(!data || Array.isArray(data) || typeof data.company_name!=='string' || !data.company_name.trim() || data.company_name.length>120 || !Array.isArray(data.rounds)) throw Error('MarketCouncil 분석 결과 파일이 아닙니다.');
  const payload=compact(Object.fromEntries(fields.filter(f=>f in data).map(f=>[f,data[f]])));
  if(new TextEncoder().encode(JSON.stringify(payload)).length>1900000) throw Error('결과 크기가 업로드 한도를 넘습니다. 더 작은 결과 파일을 선택하세요.');
  return payload;
}
export async function uploadResult(client,session,text) {
  if(!session?.user?.id) throw Error('로그인한 뒤 업로드하세요.');
  const payload=prepareResult(text);
  const bytes=new TextEncoder().encode(session.user.id+JSON.stringify(payload));
  const digest=new Uint8Array(await crypto.subtle.digest('SHA-256',bytes));
  digest[6]=(digest[6]&15)|80;digest[8]=(digest[8]&63)|128;
  const hex=Array.from(digest.slice(0,16),v=>v.toString(16).padStart(2,'0')).join('');
  const id=[hex.slice(0,8),hex.slice(8,12),hex.slice(12,16),hex.slice(16,20),hex.slice(20)].join('-');
  const {data:existing,error:readError}=await client.from('discussions').select('id').eq('id',id).maybeSingle();
  if(readError) throw Error('저장 상태를 확인하지 못했습니다. 다시 시도하세요.');
  if(existing) return {duplicate:true};
  const {error}=await client.from('discussions').insert({id,user_id:session.user.id,company_name:payload.company_name,ticker:String(payload.financial_data?.ticker||'').slice(0,30),analysis_date:payload.created_at||new Date().toISOString(),payload});
  if(error) throw Error('결과를 업로드하지 못했습니다. 로그인 상태와 인터넷 연결을 확인하세요.');
  return {duplicate:false};
}
