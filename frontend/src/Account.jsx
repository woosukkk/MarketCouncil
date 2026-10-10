import React, {useEffect, useState} from 'react';
import {supabase} from './account.js';
import Discussions from './Discussions.jsx';
import GettingStarted from './GettingStarted.jsx';
import {uploadResult} from './resultUpload.js';
import {dateLabel, resultKey} from './data.js';

export function useAccount() {
  const [session,setSession]=useState(null),[ready,setReady]=useState(false);
  useEffect(()=>{
    if(!supabase){setReady(true);return;}
    const {data:{subscription}}=supabase.auth.onAuthStateChange((_event,next)=>{setSession(next);setReady(true)});
    return()=>subscription.unsubscribe();
  },[]);
  return {session,ready};
}

export function Login({onBack}) {
  const [email,setEmail]=useState(''),[busy,setBusy]=useState(false),[message,setMessage]=useState(''),[error,setError]=useState('');
  const [githubReady,setGithubReady]=useState(false);
  useEffect(()=>{let active=true;if(supabase)fetch(import.meta.env.VITE_SUPABASE_URL+'/auth/v1/settings',{headers:{apikey:import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY}}).then(r=>r.ok?r.json():null).then(data=>{if(active)setGithubReady(data?.external?.github===true)}).catch(()=>{});return()=>{active=false}},[]);
  async function github(){
    setBusy(true);setError('');
    try{const {error}=await supabase.auth.signInWithOAuth({provider:'github',options:{redirectTo:location.origin+'/app?view=my'}});if(error)throw error;}
    catch{setError('GitHub 로그인에 연결하지 못했습니다. 잠시 후 다시 시도하세요.');setBusy(false)}
  }
  async function submit(event){
    event.preventDefault();setBusy(true);setError('');setMessage('');
    try {
      const {error}=await supabase.auth.signInWithOtp({email:email.trim(),options:{emailRedirectTo:location.origin+'/app'}});
      if(error)throw error;
      setMessage('로그인 링크를 이메일로 보냈습니다. 메일의 링크를 누르면 로그인됩니다. 처음 이용하면 계정이 함께 만들어집니다.');
    } catch {setError('이메일을 보내지 못했습니다. 주소를 확인하고 잠시 후 다시 시도해 주세요.');}
    finally {setBusy(false);}
  }
  return <section className="account-page"><button className="back" onClick={onBack}>← 리서치로 돌아가기</button><span className="eyebrow">YOUR RESEARCH SPACE</span><h1>내 관심을, 내 공간에.</h1><p>이메일로 로그인하고 관심기업과 분석을 저장하세요.</p><button className="primary" disabled={busy||!githubReady} onClick={github}>{busy?'연결 중…':githubReady?'GitHub로 시작하기':'GitHub 로그인 연결 준비 중'}</button><p>처음 로그인하면 계정이 만들어집니다. 분석 결과는 직접 공개하기 전까지 본인만 볼 수 있습니다.</p><details><summary>기존 이메일 로그인 (운영자용)</summary><form className="account-form" onSubmit={submit}><label>이메일<input type="email" autoComplete="email" required maxLength={254} value={email} onChange={e=>setEmail(e.target.value)} placeholder="you@example.com"/></label><button className="primary" disabled={busy||!supabase}>{busy?'보내는 중…':'이메일로 로그인 링크 받기'}</button></form><p className="muted">일반 사용자 이메일 발송은 아직 연결되지 않았습니다.</p></details>{message&&<p role="status" className="account-notice">{message}</p>}{error&&<p role="alert">{error}</p>}{!supabase&&<p role="alert">로그인 연결을 준비하고 있습니다.</p>}</section>;
}

export function SaveActions({session,record,onLogin}) {
  const [busy,setBusy]=useState(false),[message,setMessage]=useState('');
  useEffect(()=>{setMessage('')},[record.id,session?.user.id]);
  async function save(kind){
    if(!session){onLogin();return;}
    setBusy(true);setMessage('');
    const table=kind==='company'?'watchlist':'saved_analyses';
    const item=kind==='company'?{company_key:record.ticker||record.company_name,company_name:record.company_name,ticker:record.ticker||''}:{result_key:resultKey(record.id),company_name:record.company_name,analysis_date:record.created_at||''};
    try {
      const {error}=await supabase.from(table).upsert({user_id:session.user.id,...item},{onConflict:kind==='company'?'user_id,company_key':'user_id,result_key',ignoreDuplicates:true});
      if(error)throw error;
      setMessage(kind==='company'?'관심기업에 추가했습니다.':'마이페이지에 분석을 저장했습니다.');
    }catch{setMessage('저장하지 못했습니다. 잠시 후 다시 시도해 주세요.');}
    finally{setBusy(false);}
  }
  return <div className="save-actions"><button disabled={busy} onClick={()=>save('company')}>＋ 관심기업</button><button disabled={busy} onClick={()=>save('analysis')}>☆ 분석 저장</button><span role="status">{message}</span></div>;
}

export function MyPage({session,sessions,onOpen,onLogin}) {
  const [companies,setCompanies]=useState([]),[saved,setSaved]=useState([]),[loading,setLoading]=useState(true),[error,setError]=useState(''),[busy,setBusy]=useState(false),[name,setName]=useState(''),[ticker,setTicker]=useState('');
  useEffect(()=>{
    let active=true;setCompanies([]);setSaved([]);setError('');setLoading(true);
    if(!session){setLoading(false);return;}
    Promise.all([supabase.from('watchlist').select('*').eq('user_id',session.user.id).order('created_at',{ascending:false}),supabase.from('saved_analyses').select('*').eq('user_id',session.user.id).order('created_at',{ascending:false})]).then(([a,b])=>{
      if(!active)return;if(a.error||b.error){setError('목록을 불러오지 못했습니다. 새로고침해 다시 시도해 주세요.');return;}setCompanies(a.data);setSaved(b.data);
    }).catch(()=>{if(active)setError('목록을 불러오지 못했습니다.');}).finally(()=>{if(active)setLoading(false)});
    return()=>{active=false};
  },[session?.user.id]);
  async function add(event){
    event.preventDefault();setBusy(true);setError('');
    try{
      const company_name=name.trim(),code=ticker.trim().toUpperCase();
      if(!company_name)throw Error();
      const {data,error}=await supabase.from('watchlist').upsert({user_id:session.user.id,company_key:code||company_name,company_name,ticker:code},{onConflict:'user_id,company_key'}).select().single();
      if(error)throw error;
      setCompanies(prev=>[data,...prev.filter(x=>x.company_key!==data.company_key)]);setName('');setTicker('');
    }catch{setError('관심기업을 추가하지 못했습니다. 입력을 확인하고 다시 시도해 주세요.');}finally{setBusy(false)}
  }
  async function remove(table,key,value){
    setBusy(true);setError('');
    try{
      const {error}=await supabase.from(table).delete().eq('user_id',session.user.id).eq(key,value);
      if(error)throw error;
      if(table==='watchlist')setCompanies(prev=>prev.filter(x=>x.company_key!==value));else setSaved(prev=>prev.filter(x=>x.result_key!==value));
    }catch{setError('목록에서 제거하지 못했습니다.');}finally{setBusy(false)}
  }
  const [uploadMessage,setUploadMessage]=useState(''),[uploading,setUploading]=useState(false),[revision,setRevision]=useState(0);
  async function importResult(event){
    const input=event.target,file=input.files?.[0];if(!file)return;
    setUploading(true);setUploadMessage('');
    try{
      if(file.size>10*1024*1024)throw Error('10MB 이하의 분석 JSON 파일을 선택하세요.');
      const result=await uploadResult(supabase,session,await file.text());
      setUploadMessage(result.duplicate?'이미 보관한 결과입니다.':'내 계정에 비공개로 보관했습니다. 아래 목록에서 확인하세요.');setRevision(v=>v+1);
    }catch(error){setUploadMessage(error.message)}finally{setUploading(false);input.value=''}
  }
  if(!session)return <section className="account-page"><h1>마이페이지</h1><GettingStarted session={session} onLogin={onLogin}/><p>로그인하면 관심기업과 저장한 분석을 볼 수 있습니다.</p><button className="primary" onClick={onLogin}>로그인하기</button></section>;
  return <section className="account-page"><span className="eyebrow">MY RESEARCH</span><h1>나의 리서치</h1><p>{session.user.email||session.user.user_metadata?.user_name||'내 계정'}</p><GettingStarted session={session} onLogin={onLogin}/><section className="result-import"><h2>PC 분석 결과 가져오기</h2><p>PC에 저장된 분석 JSON 파일을 선택하면 비공개로 보관합니다. 원문 문서와 검색 문맥은 제외합니다.</p><label>분석 JSON 파일<input type="file" accept=".json,application/json" disabled={uploading} onChange={importResult}/></label><p className="muted">Windows의 사용자 폴더 → AppData → Local → MarketCouncil → results에서 결과 파일을 찾을 수 있습니다.</p>{uploadMessage&&<p role="status">{uploadMessage}</p>}</section>{error&&<p role="alert">{error}</p>}{loading?<p role="status">개인 목록을 불러오는 중입니다…</p>:<><Discussions key={revision} session={session} onOpen={onOpen} personal/><h2>관심기업 <small>{companies.length}</small></h2><form className="company-form" onSubmit={add}><label>기업명<input required maxLength={120} value={name} onChange={e=>setName(e.target.value)} placeholder="예: SK하이닉스"/></label><label>종목코드 (선택)<input maxLength={30} value={ticker} onChange={e=>setTicker(e.target.value)} placeholder="예: 000660.KS"/></label><button className="primary" disabled={busy}>추가</button></form><p className="muted">관심기업 등록은 목록 관리 기능입니다. 새 분석을 실행하지 않습니다.</p><div className="personal-list">{companies.length===0?<p>관심기업을 추가해 보세요.</p>:companies.map(c=><article key={c.company_key}><div><h3>{c.company_name}</h3><span>{c.ticker||'종목코드 미등록'}</span></div><button disabled={busy} onClick={()=>remove('watchlist','company_key',c.company_key)}>목록에서 제거</button></article>)}</div><h2>저장한 분석 <small>{saved.length}</small></h2><div className="personal-list">{saved.length===0?<p>분석 상세에서 ‘분석 저장’을 눌러 담아 보세요.</p>:saved.map(s=>{const record=(sessions||[]).find(x=>resultKey(x.id)===s.result_key);return <article key={s.result_key}><div><h3>{s.company_name}</h3><span>{dateLabel(s.analysis_date)}</span></div><div>{record?<button onClick={()=>onOpen(record)}>분석 읽기 ↗</button>:<span className="muted">현재 공개 목록에 없는 분석</span>}<button disabled={busy} onClick={()=>remove('saved_analyses','result_key',s.result_key)}>저장 해제</button></div></article>})}</div></>}</section>;
}
