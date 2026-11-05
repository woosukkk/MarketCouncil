import {useLanguage} from './Language.jsx';
import React,{useState,useEffect} from 'react';
import {supabase} from './account.js';
import {prepareMeasurementReport,metricText,monitoringSummary,reportTab,costText} from './adminData.js';

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
  const {t}=useLanguage();
 if(!report)return null;
 const llm=report.llm;
 return <section>
  <h2>{t("최근 분석의 단계와 API 관측")}</h2>
  {!llm?<p className="muted">{t("이 기록에는 상세 계측이 없습니다. Windows 0.6.0 이상 또는 최신 소스로 새 분석을 실행하면 단계·토큰 계측이 기록됩니다. 0.5.0은 전체 시간만 수집하며 이전 기록은 유지됩니다.")}</p>:<>
   <div className="detail-metrics">
    <div><span>{t("관측 API 요청 / 오류")}</span><strong>{t(metricText(llm.request_count))} / {t(metricText(llm.error_count))}</strong></div>
    <div><span>{t("관측 입력 / 출력 토큰")}</span><strong>{t(metricText(llm.input_tokens))} / {t(metricText(llm.output_tokens))}</strong></div>
    <div><span>{t("캐시 입력 / 추론 토큰")}</span><strong>{t(metricText(llm.cached_input_tokens))} / {t(metricText(llm.reasoning_tokens))}</strong></div>
    <div><span>{t("토큰 비용 추정 · USD")}</span><strong>{t(costText(llm))}</strong></div>
   </div>
   <p className="muted">{t(costStatus(llm))}{t(" · 사용량 확인 ")}{llm.usage_known_calls}{t("회 / 미확인 ")}{llm.usage_missing_calls}{t("회. 미확인 요청이 있으면 토큰 수는 확인된 응답의 부분합입니다. 캐시 입력은 입력에, 추론 토큰은 출력에 포함됩니다.")}</p>
   <p className="muted">{t("계정 청구액이 아닙니다. SDK 내부 재시도와 웹 검색 등 도구별 요금은 포함하지 않습니다. 관측이 없거나 비용을 알 수 없는 요청을 0원으로 처리하지 않습니다.")}</p>
   {llm.pricing&&<p className="muted">{t("단가 기준 ")}{llm.pricing.as_of} · {llm.pricing.source==='manual'?t('직접 입력한 가격'):t('OpenAI API 가격 스냅샷')} · {llm.pricing.model}{t(". 입력 / 캐시 입력 / 출력 백만 토큰당 USD ")}{llm.pricing.input_per_million} / {llm.pricing.cached_input_per_million} / {llm.pricing.output_per_million}.</p>}
   {llm.by_phase.length>0&&<div className="admin-table"><table><thead><tr><th>{t("API 단계")}</th><th>{t("요청 / 오류")}</th><th>{t("요청 시간 · 초")}</th><th>{t("관측 입력 / 출력")}</th><th>{t("토큰 비용 추정 · USD")}</th></tr></thead><tbody>{llm.by_phase.map(row=><tr key={row.phase}><td>{t(apiLabels[row.phase])}<br/><small>{row.model||t('복수 모델 또는 미확인')}</small></td><td>{row.request_count} / {row.error_count}<br/><small>{t("사용량 미확인 ")}{row.usage_missing_calls}{t("회")}</small></td><td>{t(metricText(row.duration_ms/1000))}</td><td>{t(metricText(row.input_tokens))} / {t(metricText(row.output_tokens))}</td><td>{t(costText(row))}<br/><small>{row.cost_status==='partial'?t('일부 관측 추정'):row.cost_status==='estimated'?t('관측 토큰 추정'):t('미측정')}</small></td></tr>)}</tbody></table></div>}
  </>}
  {report.stages?.length>0&&<>
   <h3>{t("시간이 긴 분석 단계")}</h3>
   <div className="admin-table"><table><thead><tr><th>{t("단계")}</th><th>{t("시간 · 초")}</th><th>{t("상태")}</th></tr></thead><tbody>{[...report.stages].sort((a,b)=>b.duration_ms-a.duration_ms).slice(0,20).map((row,index)=><tr key={row.name+'-'+index}><td>{t(stageLabels[row.name])}</td><td>{t(metricText(row.duration_ms/1000))}</td><td>{row.cached?t('완료 단계 재사용'):row.status==='success'?t('완료'):t('실패')}</td></tr>)}</tbody></table></div>
   <p className="muted">{t("긴 순서로 최대 20개를 표시합니다.")}{report.stages_truncated?t(' 원본 계측 한도를 넘은 단계는 기록에서 생략됐습니다.'):''}{t(" 재사용 기록은 이번 실행의 새 API 호출을 뜻하지 않습니다.")}</p>
  </>}
  <p className="muted">{t("병렬 작업과 상위·하위 단계는 시간이 겹칩니다. 단계 시간이나 API 요청 시간의 합은 전체 실행 시간이 아닙니다.")}</p>
 </section>;
}
function QualitySummary({report}){
  const {t}=useLanguage();
 const synthetic=report?.settings.dataset_kind==='synthetic';
 return <>
  <h2>{t("답변과 인용의 근거 품질")}</h2>
  <div className="detail-metrics">
   <div><span>{t("검토 사례")}</span><strong>{t(metricText(report?.metrics.case_count))}</strong></div>
   <div><span>{t("사람 정답 검수 범위")}</span><strong>{t(metricText(report?.metrics.review_coverage,true))}</strong></div>
   <div><span>{t("별도 예측과 비교한 사례")}</span><strong>{t(metricText(report?.metrics.compared_count))}</strong></div>
   <div><span>{synthetic?t('합성 회귀 일치율'):t('제공한 사람 정답 대비 판정 일치율')}</span><strong>{t(qualityScore(report))}</strong></div>
  </div>
  <p className="muted">{t("인용 ID·숫자가 맞는지만으로 주장이 사실이거나 인용으로 뒷받침된다고 판단하지 않습니다. 사람이 검수한 정답과 별도 예측이 모두 있는 사례만 의미 판정을 비교합니다. 정답이 없으면 미평가로 유지합니다.")}</p>
  {report&&<>
   <p className="muted">{synthetic?t('합성 사례를 사용한 회귀 검사입니다. 실제 서비스 정확도를 뜻하지 않습니다.'):t('입력 파일에 선언된 사람 정답을 기준으로 합니다. 독립 전문가 검수나 전체 서비스 정확도를 보증하지 않습니다.')}{t(" 정답 출처: ")}{t(origins[report.settings.annotation_origin])}{t(" · 예측 출처: ")}{t(origins[report.settings.prediction_origin])}.</p>
   <div className="detail-metrics">
    <div><span>{t("사람 검수 완료")}</span><strong>{report.metrics.reviewed_count}</strong></div>
    <div><span>{t("수치 검토 필요")}</span><strong>{report.metrics.numeric_review_count}</strong></div>
    <div><span>{t("인용 연결 불충족")}</span><strong>{report.metrics.identity_invalid_count}</strong></div>
    <div><span>{t("기준일 이후 근거")}</span><strong>{report.metrics.future_source_count}</strong></div>
   </div>
   <p className="muted">{t("규칙 경고는 검토가 필요한 사례 수입니다. 서로 중복될 수 있으며 의미 정답이나 할루시네이션 비율로 환산하지 않습니다. 원문과 주장은 이 관리자 보고서에 포함하지 않습니다.")}</p>
  </>}
 </>;
}
function History({reports,tab}){
  const {t,locale}=useLanguage();
 if(!reports.length)return null;
 const quality=tab==='quality',retrieval=tab==='rag';
 const chartReports=(retrieval?reports:reports.filter(row=>row.scope==='analysis')).slice(0,12);
 const chartKey=retrieval?'median_ms':'duration_ms';
 const max=Math.max(...chartReports.map(row=>row.metrics[chartKey]),1);
 return <>
  <h2>{quality?t('검토 데이터셋별 기록'):retrieval?t('평가 설정과 버전별 비교'):t('최근 측정 기록')}</h2>
  <div className="admin-table"><table><thead><tr><th>{t("측정 시각")}</th><th>{t("대상·버전")}</th>{quality?<><th>{t("정답·예측 출처")}</th><th>{t("사람 검수 / 전체")}</th><th>{t("의미 판정 일치율")}</th></>:retrieval?<><th>{t("평가 조건")}</th><th>Recall / MRR</th><th>p95 ms</th><th>{t("기업 혼입 / 미래 자료")}</th></>:<><th>{t("측정 범위")}</th><th>{t("처리 시간 · 초")}</th><th>{t("상태")}</th></>}</tr></thead><tbody>{reports.map(report=><tr key={report.id}>
   <td>{new Date(report.recorded_at).toLocaleString(locale==='en'?'en-US':'ko-KR')}</td>
   <td>{quality?(report.settings.dataset_kind==='synthetic'?t('합성 회귀'):t('실제 사례')):report.label}<br/><small>{report.version}{quality&&<><br/>{t("데이터셋 ")}{report.dataset_hash.slice(0,12)}<br/>{t("예측 ")}{report.settings.predictions_hash?.slice(0,12)||t('미제공')}</>}</small></td>
   {quality?<><td>{t(origins[report.settings.annotation_origin])} / {t(origins[report.settings.prediction_origin])}</td><td>{report.metrics.reviewed_count} / {report.metrics.case_count}<br/><small>{t("비교 ")}{report.metrics.compared_count}{t("건")}</small></td><td>{t(qualityScore(report))}<br/><small>{report.settings.dataset_kind==='synthetic'?t('합성 회귀 결과'):t('제공된 사람 정답 기준')}</small></td></>:retrieval?<><td>{report.settings.case_count}{t("문항 · k=")}{report.settings.top_k} · {report.settings.repeats}{t("회")}<br/><small>{t("모델 ")}{report.settings.model||t('미지정')}<br/>{t("데이터셋 ")}{report.dataset_hash.slice(0,12)}<br/>{t("저장소 ")}{report.settings.corpus_hash?.slice(0,12)||t('미지정')}</small></td><td>{t(metricText(report.metrics.recall,true))} / {t(metricText(report.metrics.mrr,true))}</td><td>{t(metricText(report.metrics.p95_ms))}</td><td>{t(metricText(report.metrics.mixed_company))} / {t(metricText(report.metrics.future_sources))}<br/><small>{t("기업 미상 ")}{t(metricText(report.metrics.unknown_company))}</small></td></>:<><td>{report.scope}<br/><small>{report.environment.os||t('환경 미지정')} · {report.environment.cpu_count||'—'} CPU</small></td><td>{t(metricText(report.metrics.duration_ms/1000))}</td><td>{report.status==='success'?t('성공'):t('실패')}</td></>}
  </tr>)}</tbody></table></div>
  {!quality&&chartReports.length>0&&<>
   <h2>{t("처리 시간 추이")}</h2><div className="admin-bars" role="img" aria-label={t("최근 기록의 처리 시간 비교")}>{[...chartReports].reverse().map(report=><div key={report.id}><span>{new Date(report.recorded_at).toLocaleDateString(locale==='en'?'en-US':'ko-KR')}</span><div><i style={{width:(report.metrics[chartKey]/max*100)+'%'}}/></div><span>{t(metricText(report.metrics[chartKey]))} ms</span></div>)}</div>
   <p className="muted">{t("최근 200건을 표시합니다. 그래프는 최근 12건이며 자료·모델·캐시·실행 조건이 같은 기록끼리 비교하세요.")}</p>
  </>}
 </>;
}
const readinessTypes={annual:'연간 보고서 본문',interim:'분기·반기 보고서 본문',earnings:'실적 발표 본문',report:'기타 공식 보고서 본문'};
const readinessMissing={annual_missing:'연간 보고서 본문 필요',recent_financial_missing:'최근 재무 자료 필요',earnings_missing:'실적 발표 본문 필요'};
const collectionFailures={collection_failed:'자료 수집 확인 필요',manifest_missing:'근거 묶음 없음',invalid_manifest:'근거 묶음 형식 확인 필요',download_failed:'공식 자료 다운로드 실패',source_unavailable:'공식 자료 접근 확인 필요',date_unavailable:'공시 시점 확인 필요',body_unavailable:'본문 확보 안 됨',issuer_mismatch:'기업 식별 불일치',cache_invalid:'저장 본문 검증 실패'};

export function EvidenceReadinessSummary({report}){
 const {t}=useLanguage();
 return <section>
  <h2>{t('기업별 근거 준비 현황')}</h2>
  <p className="muted">{t('문서 수는 본문을 확보한 고유 문서 수입니다. 의미 정확도나 RAG 검색 품질 점수가 아닙니다.')}</p>
  {!report?null:<>
   <div className="detail-metrics"><div><span>{t('기준일 조건 충족 기업')}</span><strong>{report.companies.filter(row=>row.status==='ready').length} / {report.companies.length}</strong></div><div><span>{t('근거 기준일')}</span><strong>{report.companies[0].as_of_date}</strong></div><div><span>{t('수집·검사 시간 · 초')}</span><strong>{t(metricText(report.metrics.duration_ms/1000))}</strong></div></div>
   <p className="muted">{t('이 기록은 표시된 기준일의 자료 확보 상태입니다. 공식 게시 전에는 오늘의 상태를 다시 검사합니다.')}</p>
   <div className="admin-table"><table><thead><tr><th>{t('기업')}</th><th>{t('자료 준비 판정')}</th><th>{t('연간')}</th><th>{t('분기·반기')}</th><th>{t('실적 발표')}</th><th>{t('기타 공식 보고서')}</th><th>{t('보완할 자료')}</th></tr></thead><tbody>{report.companies.map(row=><tr key={row.ticker}>
    <td>{row.company_name}<br/><small>{row.ticker}</small></td><td>{row.status==='ready'?t('기준일 조건 충족'):t('자료 보완 필요')}</td><td>{row.counts.annual}</td><td>{row.counts.interim}</td><td>{row.counts.earnings}</td><td>{row.counts.report}</td><td>{row.missing.length?row.missing.map(code=>t(readinessMissing[code])).join(' · '):t('최소 조건 충족')}</td>
   </tr>)}</tbody></table></div>
   <p className="muted">{t('최근 연간 보고서가 더 최신 재무 기간이면 분기 자료를 대체할 수 있습니다. 수집 작업 완료가 모든 기업의 준비 완료를 뜻하지는 않습니다.')}</p>
   {report.collection_failures.length>0&&<section><h3>{t('확인이 필요한 수집 단계')}</h3><ul>{report.collection_failures.map((row,index)=><li key={row.ticker+'-'+index}>{row.ticker} · {t(collectionFailures[row.code])}</li>)}</ul></section>}
   {report.companies.map(row=><details key={row.ticker}><summary>{row.company_name} · {t('근거 출처와 시점')}</summary><p><small>{t('근거 묶음 해시 ')}{row.corpus_hash.slice(0,16)}</small></p>{row.documents.length===0?<p>{t('검증된 본문이 없습니다.')}</p>:<ul>{row.documents.map(doc=><li key={doc.document_id}><a href={doc.source_url} target="_blank" rel="noreferrer">{t(readinessTypes[doc.document_type])}</a> · {t('발표일 ')}{doc.published_at} · {t('보고 기간 ')}{doc.report_date}<br/><small>{t('본문 식별 해시 ')}{doc.content_hash.slice(0,16)}</small></li>)}</ul>}</details>)}
  </>}
 </section>;
}
function ReadinessHistory({reports}){
 const {t,locale}=useLanguage();
 if(!reports.length)return null;
 return <section><h2>{t('근거 준비 검사 기록')}</h2><div className="admin-table"><table><thead><tr><th>{t('측정 시각')}</th><th>{t('근거 기준일')}</th><th>{t('조건 충족 / 대상 기업')}</th><th>{t('수집·검사 시간 · 초')}</th><th>{t('확인이 필요한 수집 단계')}</th></tr></thead><tbody>{reports.map(report=><tr key={report.id}><td>{new Date(report.recorded_at).toLocaleString(locale==='en'?'en-US':'ko-KR')}</td><td>{report.companies[0].as_of_date}</td><td>{report.companies.filter(row=>row.status==='ready').length} / {report.companies.length}</td><td>{t(metricText(report.metrics.duration_ms/1000))}</td><td>{report.collection_failures.length}</td></tr>)}</tbody></table></div></section>;
}
export default function Admin({session,allowed,checking}){
  const {t,locale}=useLanguage();
 const [tab,setTab]=useState('monitoring'),[rows,setRows]=useState([]),[loading,setLoading]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState(''),[busy,setBusy]=useState(false);
 useEffect(()=>{
  let active=true;setRows([]);
  if(!allowed||!session||!supabase)return;
  setLoading(true);setError('');
  supabase.from('admin_reports').select('id,kind,recorded_at,label,payload').order('recorded_at',{ascending:false}).limit(200).then(async({data,error})=>{
   if(active){
    if(error)setError('측정 기록 저장소 연결을 확인하세요.');
    else{
     const valid=[];
     for(const row of data||[]){try{const payload=await prepareMeasurementReport(row.payload);if(!active)return;if(payload.id!==row.id||payload.kind!==row.kind)throw Error();valid.push({...row,payload});}catch{if(active)setError('형식이 잘못된 기록은 표시하지 않았습니다.');}}
     if(!active)return;setRows(valid);
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
   const payload=await prepareMeasurementReport(JSON.parse(await file.text()));
   const row={id:payload.id,user_id:session.user.id,kind:payload.kind,recorded_at:payload.recorded_at,label:payload.label,payload};
   const {error}=await supabase.from('admin_reports').insert(row);
   if(error)throw Error(error.code==='23505'?'이미 저장된 측정 기록입니다.':'기록을 저장하지 못했습니다. 관리자 권한을 확인하세요. ('+(error.code||'연결 오류')+')');
   setRows(previous=>[row,...previous].sort((a,b)=>b.recorded_at.localeCompare(a.recorded_at)).slice(0,200));
   setTab(reportTab(payload));setNotice('관리자 전용 기록으로 보관했습니다.');
  }catch(error){setError(error instanceof SyntaxError?'JSON 파일 형식을 확인하세요.':error.message)}
  finally{setBusy(false);event.target.value=''}
 }
 if(checking)return <section className="account-page"><p role="status">{t("관리자 권한을 확인하고 있습니다.")}</p></section>;
 if(!allowed)return <section className="account-page"><h1>{t("관리자 페이지")}</h1><p role="alert">{t("공식 운영자 계정으로 로그인해야 접근할 수 있습니다.")}</p></section>;
 const reports=rows.map(row=>row.payload).filter(report=>reportTab(report)===tab);
 const summary=monitoringSummary(reports),latest=reports[0],analysis=reports.find(report=>report.scope==='analysis'),web=reports.find(report=>report.scope==='web_lighthouse');
 return <section className="account-page admin-page">
  <span className="eyebrow">ADMIN · MEASURED DATA</span><h1>{t("서비스 성능과 근거 품질")}</h1><p>{t("실제 측정 기록을 비교합니다. 과거 실행 시간과 AI 정확도를 추정하지 않습니다.")}</p>
  <nav className="tabs" aria-label={t("관리자 성능 페이지")}><button aria-pressed={tab==='monitoring'} className={tab==='monitoring'?'active':undefined} onClick={()=>setTab('monitoring')}>{t("운영 모니터링")}</button><button aria-pressed={tab==='rag'} className={tab==='rag'?'active':undefined} onClick={()=>setTab('rag')}>{t("RAG 벤치마크")}</button><button aria-pressed={tab==='quality'} className={tab==='quality'?'active':undefined} onClick={()=>setTab('quality')}>{t("답변 근거 품질")}</button><button aria-pressed={tab==='readiness'} className={tab==='readiness'?'active':undefined} onClick={()=>setTab('readiness')}>{t("기업별 근거")}</button></nav>
  <label className="result-import">{t("성능·품질·근거 현황 가져오기")}<input type="file" accept=".json,application/json" disabled={busy||!session} onChange={upload}/></label>
  {error&&<p role="alert">{t(error)}</p>}{notice&&<p role="status">{t(notice)}</p>}{loading&&<p role="status">{t("측정 기록을 불러오는 중입니다.")}</p>}
  {tab==='monitoring'?<>
   <h2>{t("운영 모니터링")}</h2><div className="detail-metrics"><div><span>{t("분석 실행 표본")}</span><strong>{summary.count}</strong></div><div><span>{t("분석 성공률")}</span><strong>{t(metricText(summary.successRate,true))}</strong></div><div><span>{t("평균 분석 시간 · 초")}</span><strong>{t(metricText(summary.averageMs===null?null:summary.averageMs/1000))}</strong></div><div><span>{t("최근 관측 토큰 비용 · USD")}</span><strong>{t(costText(analysis?.llm))}</strong></div></div>
   <p className="muted">{t("PC에서 측정해 업로드한 실행만 집계합니다. 미업로드 실행과 PC가 꺼진 시간은 관측하지 않습니다. 분석 성공률과 API 요청 오류는 별개이며, 서비스 전체 가용성을 뜻하지 않습니다.")}</p>
   <ApiObservations report={analysis}/>
  </>:tab==='readiness'?<EvidenceReadinessSummary report={latest}/>:tab==='quality'?<QualitySummary report={latest}/>:<>
   <h2>{t("RAG 검색 품질")}</h2><div className="detail-metrics">{[[t('정답 근거 포함률'),'recall'],[t('검색 정밀도'),'precision'],[t('정답의 검색 순위 · MRR'),'mrr'],[t('검색 지연 p95 · ms'),'p95_ms']].map(([label,key])=><div key={key}><span>{label}</span><strong>{t(metricText(latest?.metrics[key],key!=='p95_ms'))}</strong></div>)}</div>
   <p className="muted">{t("최신 검색 평가 기록 기준입니다. 정답 근거가 지정된 고정 질문으로 측정하며 모델 준비 시간은 제외합니다. 데이터셋·문서 저장소·모델·검색 개수가 같은 기록끼리 비교하세요. 답변의 의미 판정은 별도 탭에서 확인합니다.")}</p>
  </>}
  {!loading&&reports.length===0&&<div className="paper"><h3>{t("아직 측정 기록이 없습니다.")}</h3><p>{tab==='readiness'?t('PC에서 만든 6개 기업의 근거 준비 현황 JSON을 가져오세요. 공시 원문과 개인 경로는 업로드하지 않습니다.'):tab==='quality'?t('로컬 검토 파일에 사람 정답을 작성하고 별도 예측 파일과 비교한 품질 보고서를 가져오세요. 원문이 든 검토 파일은 업로드하지 마세요. 검수 전 보고서는 의미 품질을 미평가로 표시합니다.'):tab==='rag'?t('실제 문서에서 질문과 정답 근거를 지정한 평가 데이터셋을 준비한 뒤, 로컬 평가 결과를 가져오세요. 임의 점수나 예시 결과는 표시하지 않습니다.'):t('Windows 프로그램 또는 소스의 분석에서 생성되는 MarketCouncil/metrics 기록을 가져오세요. 0.6.0 이상은 단계·API 토큰·관측 비용 추정을, 0.5.0은 전체 시간만 수집합니다. 이전 실행에 새 수치를 소급 생성하지 않습니다.')}</p></div>}
  {tab==='monitoring'&&web&&<>
   <h2>{t("웹 페이지 성능 · Lighthouse")}</h2><div className="detail-metrics">{[[t('성능 점수'),'performance_score'],[t('주요 콘텐츠 표시 · LCP ms'),'lcp_ms'],[t('화면 이동 · CLS'),'cls'],[t('작업 지연 · TBT ms'),'tbt_ms']].map(([label,key])=><div key={key}><span>{label}</span><strong>{t(metricText(web.metrics[key],key==='performance_score'))}</strong></div>)}</div><p className="muted">{new Date(web.recorded_at).toLocaleString(locale==='en'?'en-US':'ko-KR')} · {web.settings.form_factor}{t(" 실험실 측정 1회 · Lighthouse ")}{web.settings.lighthouse_version}{t(". 실제 방문자 평균이나 서비스 가용성 지표가 아닙니다.")}</p>
  </>}
  {tab==='readiness'?<ReadinessHistory reports={reports}/>:<History reports={reports} tab={tab}/>}
 </section>;
}
