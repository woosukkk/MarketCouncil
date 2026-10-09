import React,{useEffect,useState} from 'react';
import {supabase} from './account.js';
import {dateLabel} from './data.js';
const labels={private:'비공개',public:'커뮤니티 공개',shared:'링크 공유'};

export default function Discussions({session,onOpen,personal=false}){
 const [editor,setEditor]=useState(false),[official,setOfficial]=useState([]);
 useEffect(()=>{let active=true;setEditor(false);if(session&&supabase)supabase.rpc('is_official_editor').then(({data})=>{if(active)setEditor(data===true)}).catch(()=>{if(active)setEditor(false)});return()=>{active=false}},[session?.user.id]);
 useEffect(()=>{if(personal||!supabase)return;let active=true;supabase.from('daily_official_discussions').select('publication_date,discussion_id').order('publication_date',{ascending:false}).then(({data})=>{if(active)setOfficial(data||[])}).catch(()=>{if(active)setOfficial([])});return()=>{active=false}},[personal]);
 const [rows,setRows]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 useEffect(()=>{
  let active=true;setRows(null);setError('');
  if(!supabase||(personal&&!session)){setRows([]);return;}
  let query=supabase.from('discussions').select(personal?'id,company_name,ticker,analysis_date,visibility,share_token':'id,company_name,ticker,analysis_date,visibility').order('created_at',{ascending:false});
  query=personal?query.eq('user_id',session.user.id):query.eq('visibility','public');
  query.then(({data,error})=>{if(active){if(error)setError('토론 목록을 불러오지 못했습니다.');else setRows(data)}}).catch(()=>{if(active)setError('연결을 확인해 주세요.')});
  return()=>{active=false};
 },[personal,session?.user.id]);
 async function visibility(row,mode){
  if(!window.confirm(mode==='public'?'이 토론의 내용과 인용 근거를 커뮤니티에 공개할까요?':mode==='shared'?'링크를 가진 사람은 로그인 없이 읽을 수 있습니다. 공유 링크를 만들까요?':'토론을 비공개로 바꾸고 기존 공유 링크를 해제할까요?'))return;
  setBusy(true);setError('');
  try{
   const {data,error}=await supabase.from('discussions').update({visibility:mode,share_token:mode==='shared'?crypto.randomUUID():null}).eq('id',row.id).eq('user_id',session.user.id).select('id,visibility,share_token').single();
   if(error)throw error;setRows(prev=>prev.map(item=>item.id===row.id?{...item,...data}:item));
  }catch{setError('공개 범위를 바꾸지 못했습니다.');}finally{setBusy(false)}
 }
 async function chooseOfficial(row){
  if(!window.confirm('이 토론을 오늘의 공식 공개 토론으로 지정할까요? 오늘 기존 지정이 있으면 바뀝니다. 이전 토론은 공개 상태로 남으며 별도로 비공개로 바꿀 수 있습니다.'))return;
  setBusy(true);setError('');
  try{const {error}=await supabase.rpc('select_daily_official',{discussion:row.id});if(error)throw error;setRows(prev=>prev.map(x=>x.id===row.id?{...x,visibility:'public',share_token:null}:x));}
  catch{setError('공식 토론을 지정하지 못했습니다.');}finally{setBusy(false)}
 }
 async function open(row){
  setBusy(true);setError('');
  try{const {data,error}=await supabase.from('discussions').select('id,company_name,ticker,analysis_date,payload').eq('id',row.id).single();if(error)throw error;onOpen({...data,created_at:data.analysis_date,personal:true});}
  catch{setError('토론을 열 수 없습니다. 공개 범위가 바뀌었을 수 있습니다.');}finally{setBusy(false)}
 }
 return <section className="account-page"><span className="eyebrow">{personal?'MY DISCUSSIONS':'COMMUNITY'}</span><h2>{personal?'내가 실행한 토론':'공유된 토론'}</h2><p>{personal?'PC 프로그램에서 업로드한 결과입니다. 처음에는 본인만 볼 수 있습니다.':'작성자가 직접 공개한 토론을 읽고 근거를 비교하세요.'}</p>{error&&<p role="alert">{error}</p>}{rows===null&&!error?<p role="status">토론을 불러오는 중입니다…</p>:rows?.length===0?<p>아직 {personal?'업로드한':'공개된'} 토론이 없습니다.</p>:<div className="personal-list">{rows?.map(row=><article key={row.id}><div><h3>{row.company_name}</h3>{!personal&&official.some(x=>x.discussion_id===row.id)&&<strong className="official-badge">공식 토론 · {official.find(x=>x.discussion_id===row.id).publication_date}</strong>}<span>{dateLabel(row.analysis_date)} · {labels[row.visibility]}</span></div><div><button disabled={busy} onClick={()=>open(row)}>토론 읽기 ↗</button>{personal&&<>{editor&&<button disabled={busy} onClick={()=>chooseOfficial(row)}>오늘의 공식 토론 지정</button>}<button disabled={busy} onClick={()=>visibility(row,'public')}>커뮤니티 게시</button><button disabled={busy} onClick={()=>visibility(row,'shared')}>링크 공유</button>{row.visibility!=='private'&&<button disabled={busy} onClick={()=>visibility(row,'private')}>비공개로 전환</button>}</>}</div>{personal&&row.share_token&&<label className="share-link">공유 링크<input readOnly value={location.origin+'/app?share='+row.share_token} onFocus={e=>e.target.select()}/><small>이 링크를 복사해 공유하세요. 새 링크를 만들거나 비공개로 바꾸면 이전 링크는 해제됩니다.</small></label>}</article>)}</div>}</section>;
}
