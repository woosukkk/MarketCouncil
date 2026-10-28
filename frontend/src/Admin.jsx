import React,{useState,useEffect} from 'react';
import {supabase} from './account.js';
import {measurementReport,metricText,monitoringSummary,reportTab,costText} from './adminData.js';

const stageLabels={collect:'공통 근거 수집',financial_data:'금융 자료',valuation:'재무 지표',filing_search:'공식 공시 검색',bull_report_search:'Bull 리포트 검색',bear_report_search:'Bear 리포트 검색',report_context:'리포트 문맥 구성',web_collection:'웹 자료 수집',source_classification:'웹 자료 분류',evidence_resolution:'근거 연결',web_context:'웹 문맥 구성',history:'과거 자료 수집',regime:'시장 국면',regime_reasons:'국면별 근거',bull_initial:'Bull 최초 분석',bear_initial:'Bear 최초 분석',sentiment:'시장 반응 정리',shorts:'영상 자료 수집',video_topics:'영상 의제',video_summary:'영상 요약',create_agenda:'토론 의제',bull_turn:'Bull 토론 발언',bear_turn:'Bear 토론 발언',moderator_review:'중재 검토',summarize:'최종 요약',navigation:'후속 쟁점'};
const apiLabels={source_collection:'웹 자료 분류',bull_initial:'Bull 최초 분석',bear_initial:'Bear 최초 분석',regime_reasons:'국면별 근거',shorts_debate_topics:'영상 의제',video_summary:'영상 요약',debate_navigation:'후속 쟁점',debate_agenda:'토론 의제',debate_review:'중재 검토',debate_summary:'최종 요약',bull_debate_turn:'Bull 토론 발언',bear_debate_turn:'Bear 토론 발언',report_source_collection:'리포트 출처',bull_web_search:'Bull 웹 검색',bear_web_search:'Bear 웹 검색',unclassified:'분류되지 않은 호출'};
const origins={human:'사람 검토',model:'모델 판단',unreviewed:'미검수',mixed:'혼합'};
const qualityScore=report=>report?.metrics.semantic_accuracy===null||report?.metrics.semantic_accuracy===undefined?'미평가':metricText(report.metrics.semantic_accuracy,true);
const costStatus=llm=>llm?.cost_status==='partial'?'관측한 일부 호출의 토큰 비용 추정':llm?.cost_status==='estimated'?'관측 응답의 토큰 비용 추정':'단가 또는 사용량 미측정';

export function useAdmin(session){
 const [allowed,setAllowed]=useState(false),[checking,setChecking]=useState(true);
 useEffect(()=>{
  let active=true;
  setAllowed(false);setChecking(true);
  if(!supabase||!session){setChecking(false);return;}
  supabase.rpc('is_official_editor').then(({data,error})=>{if(active){setAllowed(!error&&data===true);setChecking(false)}}).catch(()=>{if(active)setChecking(false)});
  return()=>{active=false};
 },[session?.user.id]);
 return {allowed,checking};
}

function ApiObservations({report}){
 if(!report)return null;
 const llm=report.llm;
 return <section>
  <h2>최근 분석의 단계와 API 관측</h2>
  {!llm?<p className="muted">이 기록에는 상세 계측이 없습니다. 현재 다운로드 0.5.0은 전체 시간만 수집합니다. 새 단계·토큰 계측은 업데이트한 소스의 다음 실행부터 기록됩니다.</p>:<>
   <div className="detail-metrics">
    <div><span>관측 API 요청 / 오류</span><strong>{metricText(llm.request_count)} / {metricText(llm.error_count)}</strong></div>
    <div><span>관측 입력 / 출력 토큰</span><strong>{metricText(llm.input_tokens)} / {metricText(llm.output_tokens)}</strong></div>
    <div><span>캐시 입력 / 추론 토큰</span><strong>{metricText(llm.cached_input_tokens)} / {metricText(llm.reasoning_tokens)}</strong></div>
    <div><span>토큰 비용 추정 · USD</span><strong>{costText(llm)}</strong></div>
   </div>
   <p className="muted">{costStatus(llm)} · 사용량 확인 {llm.usage_known_calls}회 / 미확인 {llm.usage_missing_calls}회. 미확인 요청이 있으면 토큰 수는 확인된 응답의 부분합입니다. 캐시 입력은 입력에, 추론 토큰은 출력에 포함됩니다.</p>
   <p className="muted">계정 청구액이 아닙니다. SDK 내부 재시도와 웹 검색 등 도구별 요금은 포함하지 않습니다. 관측이 없거나 비용을 알 수 없는 요청을 0원으로 처리하지 않습니다.</p>
   {llm.pricing&&<p className="muted">단가 기준 {llm.pricing.as_of} · {llm.pricing.source==='manual'?'직접 입력한 가격':'OpenAI API 가격 스냅샷'} · {llm.pricing.model}. 입력 / 캐시 입력 / 출력 백만 토큰당 USD {llm.pricing.input_per_million} / {llm.pricing.cached_input_per_million} / {llm.pricing.output_per_million}.</p>}
   {llm.by_phase.length>0&&<div className="admin-table"><table><thead><tr><th>API 단계</th><th>요청 / 오류</th><th>요청 시간 · 초</th><th>관측 입력 / 출력</th><th>토큰 비용 추정 · USD</th></tr></thead><tbody>{llm.by_phase.map(row=><tr key={row.phase}><td>{apiLabels[row.phase]}<br/><small>{row.model||'복수 모델 또는 미확인'}</small></td><td>{row.request_count} / {row.error_count}<br/><small>사용량 미확인 {row.usage_missing_calls}회</small></td><td>{metricText(row.duration_ms/1000)}</td><td>{metricText(row.input_tokens)} / {metricText(row.output_tokens)}</td><td>{costText(row)}<br/><small>{row.cost_status==='partial'?'일부 관측 추정':row.cost_status==='estimated'?'관측 토큰 추정':'미측정'}</small></td></tr>)}</tbody></table></div>}
  </>}
  {report.stages?.length>0&&<>
   <h3>시간이 긴 분석 단계</h3>
   <div className="admin-table"><table><thead><tr><th>단계</th><th>시간 · 초</th><th>상태</th></tr></thead><tbody>{[...report.stages].sort((a,b)=>b.duration_ms-a.duration_ms).slice(0,20).map((row,index)=><tr key={row.name+'-'+index}><td>{stageLabels[row.name]}</td><td>{metricText(row.duration_ms/1000)}</td><td>{row.cached?'완료 단계 재사용':row.status==='success'?'완료':'실패'}</td></tr>)}</tbody></table></div>
   <p className="muted">긴 순서로 최대 20개를 표시합니다.{report.stages_truncated?' 원본 계측 한도를 넘은 단계는 기록에서 생략됐습니다.':''} 재사용 기록은 이번 실행의 새 API 호출을 뜻하지 않습니다.</p>
  </>}
  <p className="muted">병렬 작업과 상위·하위 단계는 시간이 겹칩니다. 단계 시간이나 API 요청 시간의 합은 전체 실행 시간이 아닙니다.</p>
 </section>;
}
function QualitySummary({report}){
 const synthetic=report?.settings.dataset_kind==='synthetic';
 return <>
  <h2>답변과 인용의 근거 품질</h2>
  <div className="detail-metrics">
   <div><span>검토 사례</span><strong>{metricText(report?.metrics.case_count)}</strong></div>
   <div><span>사람 정답 검수 범위</span><strong>{metricText(report?.metrics.review_coverage,true)}</strong></div>
   <div><span>별도 예측과 비교한 사례</span><strong>{metricText(report?.metrics.compared_count)}</strong></div>
   <div><span>{synthetic?'합성 회귀 일치율':'제공한 사람 정답 대비 판정 일치율'}</span><strong>{qualityScore(report)}</strong></div>
  </div>
  <p className="muted">인용 ID·숫자가 맞는지만으로 주장이 사실이거나 인용으로 뒷받침된다고 판단하지 않습니다. 사람이 검수한 정답과 별도 예측이 모두 있는 사례만 의미 판정을 비교합니다. 정답이 없으면 미평가로 유지합니다.</p>
  {report&&<>
   <p className="muted">{synthetic?'합성 사례를 사용한 회귀 검사입니다. 실제 서비스 정확도를 뜻하지 않습니다.':'입력 파일에 선언된 사람 정답을 기준으로 합니다. 독립 전문가 검수나 전체 서비스 정확도를 보증하지 않습니다.'} 정답 출처: {origins[report.settings.annotation_origin]} · 예측 출처: {origins[report.settings.prediction_origin]}.</p>
   <div className="detail-metrics">
    <div><span>사람 검수 완료</span><strong>{report.metrics.reviewed_count}</strong></div>
    <div><span>수치 검토 필요</span><strong>{report.metrics.numeric_review_count}</strong></div>
    <div><span>인용 연결 불충족</span><strong>{report.metrics.identity_invalid_count}</strong></div>
    <div><span>기준일 이후 근거</span><strong>{report.metrics.future_source_count}</strong></div>
   </div>
   <p className="muted">규칙 경고는 검토가 필요한 사례 수입니다. 서로 중복될 수 있으며 의미 정답이나 할루시네이션 비율로 환산하지 않습니다. 원문과 주장은 이 관리자 보고서에 포함하지 않습니다.</p>
  </>}
 </>;
}
function History({reports,tab}){
 if(!reports.length)return null;
 const quality=tab==='quality',retrieval=tab==='rag';
 const chartReports=(retrieval?reports:reports.filter(row=>row.scope==='analysis')).slice(0,12);
 const chartKey=retrieval?'median_ms':'duration_ms';
 const max=Math.max(...chartReports.map(row=>row.metrics[chartKey]),1);
 return <>
  <h2>{quality?'검토 데이터셋별 기록':retrieval?'평가 설정과 버전별 비교':'최근 측정 기록'}</h2>
  <div className="admin-table"><table><thead><tr><th>측정 시각</th><th>대상·버전</th>{quality?<><th>정답·예측 출처</th><th>사람 검수 / 전체</th><th>의미 판정 일치율</th></>:retrieval?<><th>평가 조건</th><th>Recall / MRR</th><th>p95 ms</th><th>기업 혼입 / 미래 자료</th></>:<><th>측정 범위</th><th>처리 시간 · 초</th><th>상태</th></>}</tr></thead><tbody>{reports.map(report=><tr key={report.id}>
   <td>{new Date(report.recorded_at).toLocaleString('ko-KR')}</td>
   <td>{quality?(report.settings.dataset_kind==='synthetic'?'합성 회귀':'실제 사례'):report.label}<br/><small>{report.version}{quality&&<><br/>데이터셋 {report.dataset_hash.slice(0,12)}<br/>예측 {report.settings.predictions_hash?.slice(0,12)||'미제공'}</>}</small></td>
   {quality?<><td>{origins[report.settings.annotation_origin]} / {origins[report.settings.prediction_origin]}</td><td>{report.metrics.reviewed_count} / {report.metrics.case_count}<br/><small>비교 {report.metrics.compared_count}건</small></td><td>{qualityScore(report)}<br/><small>{report.settings.dataset_kind==='synthetic'?'합성 회귀 결과':'제공된 사람 정답 기준'}</small></td></>:retrieval?<><td>{report.settings.case_count}문항 · k={report.settings.top_k} · {report.settings.repeats}회<br/><small>모델 {report.settings.model||'미지정'}<br/>데이터셋 {report.dataset_hash.slice(0,12)}<br/>저장소 {report.settings.corpus_hash?.slice(0,12)||'미지정'}</small></td><td>{metricText(report.metrics.recall,true)} / {metricText(report.metrics.mrr,true)}</td><td>{metricText(report.metrics.p95_ms)}</td><td>{metricText(report.metrics.mixed_company)} / {metricText(report.metrics.future_sources)}<br/><small>기업 미상 {metricText(report.metrics.unknown_company)}</small></td></>:<><td>{report.scope}<br/><small>{report.environment.os||'환경 미지정'} · {report.environment.cpu_count||'—'} CPU</small></td><td>{metricText(report.metrics.duration_ms/1000)}</td><td>{report.status==='success'?'성공':'실패'}</td></>}
  </tr>)}</tbody></table></div>
  {!quality&&chartReports.length>0&&<>
   <h2>처리 시간 추이</h2><div className="admin-bars" role="img" aria-label="최근 기록의 처리 시간 비교">{[...chartReports].reverse().map(report=><div key={report.id}><span>{new Date(report.recorded_at).toLocaleDateString('ko-KR')}</span><div><i style={{width:(report.metrics[chartKey]/max*100)+'%'}}/></div><span>{metricText(report.metrics[chartKey])} ms</span></div>)}</div>
   <p className="muted">최근 200건을 표시합니다. 그래프는 최근 12건이며 자료·모델·캐시·실행 조건이 같은 기록끼리 비교하세요.</p>
  </>}
 </>;
}
export default function Admin({session,allowed,checking}){
 const [tab,setTab]=useState('monitoring'),[rows,setRows]=useState([]),[loading,setLoading]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState(''),[busy,setBusy]=useState(false);
 useEffect(()=>{
  let active=true;setRows([]);
  if(!allowed||!session||!supabase)return;
  setLoading(true);setError('');
  supabase.from('admin_reports').select('id,kind,recorded_at,label,payload').order('recorded_at',{ascending:false}).limit(200).then(({data,error})=>{
   if(active){
    if(error)setError('측정 기록 저장소 연결을 확인하세요.');
    else{
     const valid=[];
     for(const row of data||[]){try{const payload=measurementReport(row.payload);if(payload.id!==row.id||payload.kind!==row.kind)throw Error();valid.push({...row,payload});}catch{setError('형식이 잘못된 기록은 표시하지 않았습니다.');}}
     setRows(valid);
    }
    setLoading(false);
   }
  }).catch(()=>{if(active){setError('기록을 불러오지 못했습니다.');setLoading(false)}});
  return()=>{active=false};
 },[allowed,session?.user.id]);
 async function upload(event){
  const file=event.target.files?.[0];if(!file)return;
  setBusy(true);setError('');setNotice('');
  try{
   if(file.size>1024*1024)throw Error('1MB 이하의 성능 기록을 선택하세요.');
   const payload=measurementReport(JSON.parse(await file.text()));
   const row={id:payload.id,user_id:session.user.id,kind:payload.kind,recorded_at:payload.recorded_at,label:payload.label,payload};
   const {error}=await supabase.from('admin_reports').insert(row);
   if(error)throw Error(error.code==='23505'?'이미 저장된 측정 기록입니다.':'기록을 저장하지 못했습니다. 관리자 권한을 확인하세요. ('+(error.code||'연결 오류')+')');
   setRows(previous=>[row,...previous].sort((a,b)=>b.recorded_at.localeCompare(a.recorded_at)).slice(0,200));
   setTab(reportTab(payload));setNotice('관리자 전용 기록으로 보관했습니다.');
  }catch(error){setError(error instanceof SyntaxError?'JSON 파일 형식을 확인하세요.':error.message)}
  finally{setBusy(false);event.target.value=''}
 }
 if(checking)return <section className="account-page"><p role="status">관리자 권한을 확인하고 있습니다.</p></section>;
 if(!allowed)return <section className="account-page"><h1>관리자 페이지</h1><p role="alert">공식 운영자 계정으로 로그인해야 접근할 수 있습니다.</p></section>;
 const reports=rows.map(row=>row.payload).filter(report=>reportTab(report)===tab);
 const summary=monitoringSummary(reports),latest=reports[0],analysis=reports.find(report=>report.scope==='analysis'),web=reports.find(report=>report.scope==='web_lighthouse');
 return <section className="account-page admin-page">
  <span className="eyebrow">ADMIN · MEASURED DATA</span><h1>서비스 성능과 근거 품질</h1><p>실제 측정 기록을 비교합니다. 과거 실행 시간과 AI 정확도를 추정하지 않습니다.</p>
  <nav className="tabs" aria-label="관리자 성능 페이지"><button aria-pressed={tab==='monitoring'} className={tab==='monitoring'?'active':undefined} onClick={()=>setTab('monitoring')}>운영 모니터링</button><button aria-pressed={tab==='rag'} className={tab==='rag'?'active':undefined} onClick={()=>setTab('rag')}>RAG 벤치마크</button><button aria-pressed={tab==='quality'} className={tab==='quality'?'active':undefined} onClick={()=>setTab('quality')}>답변 근거 품질</button></nav>
  <label className="result-import">성능·품질 기록 가져오기<input type="file" accept=".json,application/json" disabled={busy||!session} onChange={upload}/></label>
  {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}{loading&&<p role="status">측정 기록을 불러오는 중입니다.</p>}
  {tab==='monitoring'?<>
   <h2>운영 모니터링</h2><div className="detail-metrics"><div><span>분석 실행 표본</span><strong>{summary.count}</strong></div><div><span>분석 성공률</span><strong>{metricText(summary.successRate,true)}</strong></div><div><span>평균 분석 시간 · 초</span><strong>{metricText(summary.averageMs===null?null:summary.averageMs/1000)}</strong></div><div><span>최근 관측 토큰 비용 · USD</span><strong>{costText(analysis?.llm)}</strong></div></div>
   <p className="muted">PC에서 측정해 업로드한 실행만 집계합니다. 미업로드 실행과 PC가 꺼진 시간은 관측하지 않습니다. 분석 성공률과 API 요청 오류는 별개이며, 서비스 전체 가용성을 뜻하지 않습니다.</p>
   <ApiObservations report={analysis}/>
  </>:tab==='quality'?<QualitySummary report={latest}/>:<>
   <h2>RAG 검색 품질</h2><div className="detail-metrics">{[['정답 근거 포함률','recall'],['검색 정밀도','precision'],['정답의 검색 순위 · MRR','mrr'],['검색 지연 p95 · ms','p95_ms']].map(([label,key])=><div key={key}><span>{label}</span><strong>{metricText(latest?.metrics[key],key!=='p95_ms')}</strong></div>)}</div>
   <p className="muted">최신 검색 평가 기록 기준입니다. 정답 근거가 지정된 고정 질문으로 측정하며 모델 준비 시간은 제외합니다. 데이터셋·문서 저장소·모델·검색 개수가 같은 기록끼리 비교하세요. 답변의 의미 판정은 별도 탭에서 확인합니다.</p>
  </>}
  {!loading&&reports.length===0&&<div className="paper"><h3>아직 측정 기록이 없습니다.</h3><p>{tab==='quality'?'로컬 검토 파일에 사람 정답을 작성하고 별도 예측 파일과 비교한 품질 보고서를 가져오세요. 원문이 든 검토 파일은 업로드하지 마세요. 검수 전 보고서는 의미 품질을 미평가로 표시합니다.':tab==='rag'?'실제 문서에서 질문과 정답 근거를 지정한 평가 데이터셋을 준비한 뒤, 로컬 평가 결과를 가져오세요. 임의 점수나 예시 결과는 표시하지 않습니다.':'Windows 프로그램 0.5.0 이상 또는 소스의 분석에서 생성되는 MarketCouncil/metrics 기록을 가져오세요. 0.5.0은 전체 시간만 수집하고 새 상세 계측은 소스의 다음 실행부터 기록됩니다. 이전 실행에 새 수치를 소급 생성하지 않습니다.'}</p></div>}
  {tab==='monitoring'&&web&&<>
   <h2>웹 페이지 성능 · Lighthouse</h2><div className="detail-metrics">{[['성능 점수','performance_score'],['주요 콘텐츠 표시 · LCP ms','lcp_ms'],['화면 이동 · CLS','cls'],['작업 지연 · TBT ms','tbt_ms']].map(([label,key])=><div key={key}><span>{label}</span><strong>{metricText(web.metrics[key],key==='performance_score')}</strong></div>)}</div><p className="muted">{new Date(web.recorded_at).toLocaleString('ko-KR')} · {web.settings.form_factor} 실험실 측정 1회 · Lighthouse {web.settings.lighthouse_version}. 실제 방문자 평균이나 서비스 가용성 지표가 아닙니다.</p>
  </>}
  <History reports={reports} tab={tab}/>
 </section>;
}
