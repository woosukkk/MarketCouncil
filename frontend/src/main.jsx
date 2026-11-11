import {useLanguage, LanguageSwitch, LanguageProvider} from './Language.jsx';
import {withLanguage} from './language.js';
import React, {useCallback, useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {dateLabel, filterSessions, resultsUrl, mergeLibrary} from './data.js';
import './style.css';
import './landing.css';
import Landing from './Landing.jsx';
import CompanyResearch,{matchesCompany} from './CompanyResearch.jsx';
import LibraryPeriods from './LibraryPeriods.jsx';
import Admin,{useAdmin} from './Admin.jsx';
import {supabase} from './account.js';
import Discussions from './Discussions.jsx';
import {useAccount, Login, MyPage, SaveActions} from './Account.jsx';
import {readResult} from './resultValidation.js';
import {watchPageRefresh} from './pageRefresh.js';
import {Arrow, Detail, ResultBoundary} from './DebateDetail.jsx';
import {transition} from './transition.js';

const Relationships = import.meta.env.DEV ? React.lazy(() => import('./Relationships.jsx')) : null;


function App({navigate}) {
  const {t,locale}=useLanguage();
  const {session,ready}=useAccount();
  const admin=useAdmin(session);
  const [view,setView]=useState((Relationships ? ['my','admin','relationships'] : ['my','admin']).includes(new URLSearchParams(location.search).get('view'))?new URLSearchParams(location.search).get('view'):'library'),[authError,setAuthError]=useState(()=>new URLSearchParams(location.search).has('error')?'로그인을 완료하지 못했습니다. 다시 시도해 주세요. 문제가 계속되면 운영자에게 알려주세요.':'');
  useEffect(()=>{if(session)setView(current=>current==='login'?'my':current)},[session]);
  const login=()=>{setSelected(null);setView('login')};
  async function logout(){const {error}=await supabase.auth.signOut();if(error)setAuthError('로그아웃하지 못했습니다. 다시 시도해 주세요.');else {setAuthError('');setView('library');setSelected(null)}}
  const [sessions,setSessions]=useState(null),[selected,setSelected]=useState(null),[data,setData]=useState(null),[error,setError]=useState(''),[query,setQuery]=useState(''),[companyTicker,setCompanyTicker]=useState('');
  const [libraryNotice,setLibraryNotice]=useState(''),[libraryError,setLibraryError]=useState(''),[libraryRevision,setLibraryRevision]=useState(0);
  const refreshLibrary=useCallback(()=>setLibraryRevision(value=>value+1),[]);
  useEffect(()=>watchPageRefresh(refreshLibrary),[refreshLibrary]);
  useEffect(()=>{let active=true;
    async function load(){
      setLibraryError('');
      let archive=[];let archiveFailed=false;
      try{const response=await fetch(resultsUrl('index.json'),{cache:'no-store'});if(!response.ok)throw Error();archive=await response.json();if(!Array.isArray(archive))throw Error();}catch{archiveFailed=true;}
      try{
        if(!supabase){if(archiveFailed)throw Error();if(active){setSessions(archive);setLibraryNotice('');}return;}
        const {data:dates,error:dateError}=await supabase.from('daily_official_discussions').select('publication_date,discussion_id').order('publication_date',{ascending:false}).limit(200);
        if(dateError)throw dateError;
        let rows=[];
        if(dates.length){const {data,error}=await supabase.from('discussions').select('id,company_name,ticker,analysis_date,visibility,summary:payload->navigation->>overview,issues:payload->navigation->issues').eq('visibility','public').in('id',dates.map(x=>x.discussion_id));if(error)throw error;rows=data;}
        if(active){setSessions(mergeLibrary(archive,dates,rows));setLibraryNotice(archiveFailed?'기존 아카이브를 불러오지 못해 공식 토론만 표시합니다.':'');}
      }catch{if(active){if(archive.length){setSessions(archive);setLibraryNotice('공식 토론을 불러오지 못했습니다. 새로고침해 다시 확인하세요.');}else setLibraryError('목록을 불러올 수 없습니다.');}}
    }
    load();return()=>{active=false};
  },[libraryRevision,session?.user.id]);
  useEffect(()=>{
    if(!selected)return;
    let active=true;
    const controller=new AbortController();
    setData(null);setError('');
    async function load(){
      try{
        let payload;
        if(Object.hasOwn(selected,'payload'))payload=selected.payload;
        else if(selected.discussion){
          const {data,error}=await supabase.from('discussions').select('payload').eq('id',selected.id).eq('visibility','public').single();
          if(error)throw Error('토론이 비공개로 바뀌었거나 불러올 수 없습니다.');
          payload=data?.payload;
        }else{
          const response=await fetch(resultsUrl(`${selected.id}.json`),{signal:controller.signal});
          if(!response.ok)throw Error('분석 결과를 불러올 수 없습니다.');
          payload=await response.json();
        }
        const checked=readResult(payload);
        if(active)setData(checked);
      }catch(error){if(active&&error.name!=='AbortError')setError(error.message||'분석 결과를 불러올 수 없습니다.');}
    }
    load();return()=>{active=false;controller.abort()};
  },[selected]);
  const open=s=>{setView('library');transition(()=>setSelected(s));window.scrollTo({top:0,behavior:'instant'})};
  const back=()=>{history.replaceState({},'',withLanguage('/app',locale));setView('library');transition(()=>{setSelected(null);setError('')});window.scrollTo({top:0,behavior:'instant'})};
  useEffect(()=>{
    const token=new URLSearchParams(location.search).get('share');
    if(!token||!supabase)return;
    if(!/^[a-f0-9-]{36}$/i.test(token)){setError('유효한 공유 링크가 아닙니다.');return;}
    let active=true;
    supabase.rpc('read_shared_discussion',{token}).then(({data,error})=>{if(active){if(error||!data)setError('공유가 해제됐거나 없는 토론입니다.');else setSelected({...data,personal:true,created_at:data.analysis_date})}}).catch(()=>{if(active)setError('공유된 토론을 불러오지 못했습니다.')});
    return()=>{active=false};
  },[]);
  const filtered=filterSessions(sessions||[],query).filter(row=>matchesCompany(row,companyTicker));
  return <div className="shell"><aside className="sidebar"><button className="brand" onClick={back}><span className="brand-mark">M<span>c</span></span><span>MarketCouncil<small>INVESTMENT RESEARCH</small></span></button><a className="home-link" href={withLanguage("/",locale)} onClick={e=>{if(e.button===0&&!e.metaKey&&!e.ctrlKey&&!e.shiftKey&&!e.altKey){e.preventDefault();navigate('/')}}}>{t("← 소개 페이지")}</a><div className="sidebar-label">WORKSPACE</div><button className={view==='library'?'side-link active':'side-link'} onClick={back}><span>▦</span>{t(" 리서치 라이브러리 ")}<span>↗</span></button>{Relationships&&<button className={view==='relationships'?'side-link active':'side-link'} onClick={()=>{setSelected(null);setView('relationships')}}><span>⌘</span>{t("기업 관계")}</button>}<button className="side-link" onClick={()=>{setSelected(null);setView('my')}}>{t("☆ 마이페이지")}</button><div className="sidebar-bottom"><div className="orb">↗ ↘</div><strong>{t("두 관점, 더 깊은 판단.")}</strong><p>{t("상승과 하락의 가설을")}<br/>{t("같은 근거 위에서 비교합니다.")}</p><span className="demo-dot">{t("저장된 분석 아카이브")}</span></div></aside><div className="workspace"><div className="topbar"><span>Workspace <span className="slash">/</span> <b>{selected?t('분석 상세'):Relationships&&view==='relationships'?t('기업 관계'):view==='admin'?t('관리자'):view==='community'?t('커뮤니티'):view==='my'?t('마이페이지'):view==='login'?t('로그인'):t('리서치 라이브러리')}</b></span><div className="account-nav">{admin.allowed&&<button onClick={()=>{setSelected(null);setView('admin')}}>{t("관리자")}</button>}{Relationships&&<button onClick={()=>{setSelected(null);setView('relationships')}}>{t("기업 관계")}</button>}<button onClick={()=>{setSelected(null);setView('community')}}>{t("커뮤니티")}</button><a href={withLanguage("/download",locale)}>{t("PC 프로그램")}</a>{ready&&(session?<><button onClick={()=>{setSelected(null);setView('my')}}>{t("마이페이지")}</button><button onClick={logout}>{t("로그아웃")}</button></>:<button onClick={login}>{t("로그인")}</button>)}<LanguageSwitch/></div></div><main>{locale==='en'&&<p className="language-note">Interface language: English. Saved analyses, company names and quotations keep their original language.</p>}{authError&&<p role="alert">{t(authError)}</p>}{Relationships&&view==='relationships'?<React.Suspense fallback={<p role="status">{t('목록 불러오는 중')}</p>}><Relationships onResearch={ticker=>{setCompanyTicker(ticker);setQuery('');setSelected(null);setView('library');window.scrollTo({top:0,behavior:'instant'})}}/></React.Suspense>:view==='admin'?<Admin session={session} {...admin}/>:view==='community'?<Discussions session={session} onOpen={open} onChange={refreshLibrary} refreshVersion={libraryRevision}/>:view==='login'?<Login onBack={back}/>:view==='my'?<MyPage session={session} sessions={sessions} onOpen={open} onLogin={login} onChange={refreshLibrary} refreshVersion={libraryRevision}/>:error||(!selected&&libraryError) ? <div className="paper" role="alert"><h2>{t("자료를 불러오지 못했습니다")}</h2><p>{t(error||libraryError)}</p><button className="primary" onClick={()=>window.location.reload()}>{t("다시 불러오기")}</button></div> : selected ? data ? <>{!selected.personal&&<SaveActions session={session} record={selected} onLogin={login}/>}<ResultBoundary key={selected.id} onBack={back}><Detail data={data} onBack={back}/></ResultBoundary></> : <p role="status" className="loading">{t("분석 결과를 불러오는 중입니다…")}</p> : <><section className="hero"><div className="hero-copy"><span className="eyebrow">THE RESEARCH ROOM</span><h1>{t("하나의 종목,")}<br/>{t("서로 다른 ")}<em>{t("가능성.")}</em></h1><p>{t("확신보다 근거를, 결론보다 판단의 과정을.")}<br/>{t("Bull과 Bear의 토론에서 투자 가설을 살펴보세요.")}</p>{sessions?.[0] && <button className="primary" onClick={()=>open(sessions[0])}>{t("최근 토론 살펴보기 ")}<Arrow/></button>}</div><div className="hero-art" aria-hidden="true"><div className="art-grid"/><div className="art-circle"/><div className="chart-line line-up"/><div className="chart-line line-down"/><span className="art-label bull-label">BULL ↗</span><span className="art-label bear-label">BEAR ↘</span><div className="art-caption">THE VALUE OF<br/><b>ANOTHER PERSPECTIVE.</b></div></div></section><div className="overview-stats"><div><span>{t("저장된 리서치")}</span><strong>{sessions?.length ?? '—'}<small> sessions</small></strong></div><div><span>{t("분석 기업")}</span><strong>{sessions ? new Set(sessions.map(s=>s.company_name)).size : '—'}<small> company</small></strong></div><div><span>{t("최근 분석일")}</span><strong className="date-stat">{t(dateLabel(sessions?.[0]?.created_at))}</strong></div><div className="stats-note"><span className="green-dot"/><p>{t("분석 시점의 자료를 바탕으로 합니다.")}<br/><b>{t("실시간 시세와 구분해 확인하세요.")}</b></p></div></div><CompanyResearch rows={sessions} selected={companyTicker} onSelect={ticker=>{setCompanyTicker(ticker);setQuery('')}}/><section className="library">{libraryNotice&&<p role="status">{t(libraryNotice)}</p>}<div className="section-heading"><div><span className="eyebrow">RESEARCH LIBRARY</span><h2>{t("기록된 판단의 과정 ")}<span>{sessions?.length || 0}</span></h2></div><label className="search"><span aria-hidden="true">⌕</span><input aria-label={t("기업명 또는 분석 내용 검색")} placeholder={t("기업명, 날짜, 분석 내용 검색")} value={query} onChange={e=>setQuery(e.target.value)}/></label></div><div className="filter-line"><span className="filter-chip">{companyTicker||t("전체 리서치")}</span><span>{t("최신 분석순 ↓")}</span></div>{!sessions ? <p role="status">{t("리서치를 불러오는 중입니다…")}</p> : filtered.length===0 ? <div className="empty">{companyTicker&&!query?<><p>{t("아직 이 기업의 공개 분석이 없습니다.")}</p><a href={withLanguage("/download",locale)}>{t("내 PC에서 분석 준비하기 →")}</a></>:t("검색 결과가 없습니다. 다른 검색어를 입력해 주세요.")}</div> : <LibraryPeriods rows={filtered} searching={Boolean(query.trim())} renderCard={s=><button className="session-card" key={s.id} onClick={()=>open(s)}><div className="card-top"><span className="company-icon">{s.company_name.slice(0,1)}</span><span className="card-date">{t(dateLabel(s.created_at))} {s.created_at?.slice(11,16)}</span>{s.official_date?<span className="latest">{t("공식 토론")}</span>:s.id===sessions[0]?.id&&<span className="latest">LATEST</span>}</div><h3>{s.company_name} <Arrow/></h3><span className="ticker">{s.ticker || 'INVESTMENT DEBATE'}</span><p className="card-summary">{s.summary || t('상승과 하락의 논거를 비교하고, 추가로 확인할 근거를 살펴보세요.')}</p><div className="card-footer"><span>{t("의제 ")}{s.issue_count}{t("개 ")}{s.round_count!=null&&<> <i/> {s.round_count}{t("라운드")}</>}</span><span>{t("토론 읽기 →")}</span></div></button>}/>}</section></>}</main><footer><span className="footer-brand">MarketCouncil</span><p>{t("AI가 생성한 분석 기록입니다. 인용 대조 여부는 투자 가설의 정확성을 보장하지 않습니다.")}</p><span>READ. QUESTION. COMPARE.</span></footer></div></div>;
}
function Site() {
  const {t,locale}=useLanguage();
  const [path,setPath]=useState(location.pathname);
  useEffect(()=>{const pop=()=>transition(()=>setPath(location.pathname));window.addEventListener('popstate',pop);return()=>window.removeEventListener('popstate',pop)},[]);
  const navigate=next=>{const target=withLanguage(next,locale);history.pushState({},'',target);transition(()=>setPath(new URL(target,location.origin).pathname));window.scrollTo({top:0,behavior:'instant'})};
  if(path==='/download')return <div className="account-page download-page"><div className="download-language"><LanguageSwitch/></div><a href={withLanguage("/app",locale)} onClick={e=>{e.preventDefault();navigate('/app')}}>{t("← 서비스로 돌아가기")}</a><h1>{t("내 PC에서 토론 시작하기")}</h1><p>{t("Windows용 MarketCouncil을 실행하고 본인 API 키로 기업을 분석하세요. 체험판 0.9.0 · Windows 64비트 · 폴더형 ZIP.")}</p><a className="landing-cta" href="https://github.com/woosukkk/MarketCouncil/releases/download/desktop-v0.9.0/MarketCouncil-Windows.zip">{t("Windows 체험판 다운로드 ↓")}</a><p><a href="https://github.com/woosukkk/MarketCouncil/releases/tag/desktop-v0.9.0" target="_blank" rel="noreferrer">{t("업데이트 내역과 SHA-256 확인 →")}</a></p><p className="account-notice">{t("0.9.0 업데이트: 실행 전 확인 · 날짜별 실행 이력 · 오류 상세 · 웹사이트와 같은 화면.")}</p><ol><li>{t("ZIP을 한 번 풀고 MarketCouncil 폴더의 MarketCouncil.exe를 실행하세요. 함께 들어 있는 _internal 폴더를 유지하세요.")}</li><li>{t("로컬 분석은 로그인 없이 가능합니다. 웹 마이페이지에 로그인하면 결과를 계정에 보관할 수 있습니다.")}</li><li>{t("이메일 사용자는 프로그램에서 계정을 연결할 수 있습니다. GitHub 사용자는 분석 후 웹 마이페이지에서 결과 파일을 가져오세요.")}</li><li>{t("본인 OpenAI 키와 기업명을 입력하고 검색된 기업을 선택하세요. 국내 공시 원문에는 DART 키가, 미국 공시에는 SEC 요청용 연락처가 필요합니다.")}</li><li>{t("Docker Desktop과 SearXNG가 필요합니다. 분석 시 Docker와 검색 서비스를 준비합니다.")}</li><li>{t("기업 분석 탭의 기업 근거 준비·충족도 확인으로 공시와 실적 발표 본문을 먼저 준비하세요. 이 단계는 유료 AI를 호출하지 않습니다. 연간·최근 재무·실적 발표 자료가 부족하면 분석을 시작하지 않습니다. 준비 상태 탭에서 연결과 새 버전을 확인하고, 완료 후 결과 폴더를 열 수 있습니다.")}</li><li>{t("분석 결과는 PC에 저장됩니다. 원하는 결과만 비공개로 업로드하세요.")}</li><li>{t("웹 마이페이지에서 분석 JSON 파일을 가져와 비공개로 보관한 뒤, 공유 링크 또는 커뮤니티 게시를 선택하세요.")}</li></ol><p>{t("공식 운영자는 로그인 알림 설정에서 삼성전자 고정 또는 준비된 6개 기업 중 새 공시 우선·관심도(주가 변동) 선정을 고릅니다. Windows 로그인 30초 뒤 실행 이력 창이 열리고, 오늘 실행을 선택할 때만 분석과 공식 게시를 시작합니다. 닫으면 새 분석을 실행하지 않으며 오전 9시 무인 실행은 하지 않습니다. 날짜별 상태와 기록된 오류 원인을 확인하고, 실패한 오늘 작업은 기존 시도 한도 내에서 이어서 실행할 수 있습니다. 오늘 게시가 있거나 다른 작업이 실행 중이면 새 분석을 막습니다. 작업이 켠 검색 서비스와 Docker는 종료하고 기존 서비스는 유지합니다. 자격증명은 Windows 계정에 암호화해 저장합니다.")}</p><p>{t("근거 준비 대상은 삼성전자·SK하이닉스·현대차·NAVER·Apple·Microsoft입니다. 원문 출처·기업·발표일·본문 해시를 검사하며 수집에 실패한 최신 필수 자료를 과거 캐시로 대신하지 않습니다. Apple·Microsoft는 SEC 접근이 차단된 경우 공식 발행사의 PDF·DOCX 원문을 대체 경로로 수집하고 기업·보고 기간을 검증합니다. 필수 자료를 확보하지 못하면 분석을 시작하지 않습니다. 자료 충족 판정은 AI 답변 정확도나 RAG 검색 품질 점수가 아닙니다.")}</p><p>{t("0.9.0은 분석 전체·단계별 시간, 관측 API 토큰과 토큰 비용 추정을 PC의 MarketCouncil/metrics 폴더에 기록합니다. 계정 청구액과 도구 요금은 포함하지 않습니다. 기록의 원격 전송은 직접 선택하며, 관리자 페이지에서 가져올 수 있습니다. 이전 버전은 새 ZIP을 별도 폴더에 풀어 업데이트하세요. 공식 게시를 설정했다면 새 프로그램의 설정을 다시 저장해야 새 실행 경로와 로그인 알림 방식이 적용됩니다. 원본 결과와 계정 설정은 유지됩니다.")}</p><p>{t("이메일 또는 GitHub로 로그인할 수 있습니다. 이메일이 보이지 않으면 스팸함을 확인하세요.")}</p><p>{t("첫 분석 시 웹 자료 수집용 브라우저를 다운로드합니다. 모델·PDF·검색 데이터는 로컬에 보관됩니다. 프로그램은 Windows 64비트용이며 OpenAI 사용료가 발생합니다. 코드 서명이 없어 Windows에서 게시자를 확인하지 못할 수 있습니다.")}</p></div>;
  return path==='/app' || path==='/app/' ? <App navigate={navigate}/> : <Landing navigate={navigate}/>;
}
createRoot(document.getElementById('root')).render(<LanguageProvider><Site/></LanguageProvider>);
