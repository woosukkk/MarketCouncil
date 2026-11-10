import React, {useState} from 'react';
import {useLanguage, LanguageContext} from './Language.jsx';
import {safeUrl, dateLabel, statuses, issueStatus, usedSources} from './data.js';
import {transition} from './transition.js';

export const Arrow = () => <span aria-hidden="true">↗</span>;
function Badge({status}) {
  const {t}=useLanguage();
  return <span className={`badge ${status === 'RESOLVED' ? 'resolved' : ''}`}>{t(statuses[status] || status)}</span>;}
function Text({children}) {
  const {t}=useLanguage();
  return <div className="prose">{typeof children === 'string' ? children : t('확인할 자료가 없습니다.')}</div>;}
function Evidence({item}) {
  const {t}=useLanguage();
  if(typeof item !== 'object' || !item) return <blockquote>{String(item)}</blockquote>;
  const href=safeUrl(item.source_page_url || item.source_url);
  return <details className="evidence"><summary><span className="evidence-id">{item.evidence_id || t('근거')}</span><span>{item.title || item.reason || t('인용 원문')}</span><span className="verification">{item.verified === true ? t('인용 대조 완료') : t('대조 미확인')}</span></summary><div className="evidence-body"><blockquote>{item.exact_quote || item.reason || t('인용문 없음')}</blockquote>{item.reason && <p>{item.reason}</p>}<div className="metadata">{item.published_at || t('발행일 미상')}{item.page_number ? t(" · {0}쪽",{"0":item.page_number}) : ''}</div>{href && <a href={href} target="_blank" rel="noreferrer">{t("출처 원문 열기 ")}<Arrow/></a>}{item.context_text && <details className="context"><summary>{t("인용 주변 문맥")}</summary><Text>{item.context_text}</Text></details>}</div></details>;
}
function Argument({side,turn,fallback}) {
  const {t}=useLanguage();
  return <article className={`argument ${side}`}><div className="argument-label"><span>{side==='bull'?'↗':'↘'}</span>{side==='bull'?t('BULL · 상승 가설'):t('BEAR · 하락 가설')}</div><h3>{turn?.claim || fallback || t('이 라운드에 기록된 주장이 없습니다.')}</h3>{turn?.warrant && <Text>{turn.warrant}</Text>}{turn?.qualifier && <div className="condition"><strong>{t("성립 조건")}</strong><p>{turn.qualifier}</p></div>}{turn?.missing_evidence && <div className="condition"><strong>{t("추가 확인")}</strong><p>{Array.isArray(turn.missing_evidence)?turn.missing_evidence.join('\n'):turn.missing_evidence}</p></div>}{(turn?.evidence||[]).length>0 && <div className="evidence-list"><span className="eyebrow">{t("인용 근거 · ")}{turn.evidence.length}</span>{turn.evidence.map((e,i)=><Evidence key={i} item={e}/>)}</div>}</article>;
}
function Summary({data}) {
  const {t}=useLanguage();
  const s=data.moderator_summary || {};
  return <><section className="summary-lead"><span className="eyebrow">MODERATOR'S NOTE</span><h2>{t("토론이 남긴 결론")}</h2><Text>{s.summary}</Text></section><div className="summary-grid">{[['agreements',t('양측이 합의한 사실'),'01'],['unresolved_issues',t('아직 남아 있는 쟁점'),'02'],['required_evidence',t('다음에 확인할 근거'),'03']].map(([key,title,n])=><section className="paper" key={key}><span className="section-number">{n}</span><h3>{title}</h3>{s[key]?.length ? <ul className="findings">{s[key].map((v,i)=><li key={i}>{v}</li>)}</ul>:<p className="muted">{t("저장된 내용이 없습니다.")}</p>}</section>)}</div></>;
}
function Debate({data}) {
  const {t}=useLanguage();
  const [issue,setIssue]=useState(0), [round,setRound]=useState(0);
  const agenda=data.agenda || [], selected=agenda[issue], r=data.rounds?.[round];
  if(!selected) return <div className="paper"><h2>{t("분석·반론 원문")}</h2><div className="comparison"><Text>{data.bull_analysis}</Text><Text>{data.bear_analysis}</Text></div></div>;
  const guide=data.navigation?.issues?.find(x=>x.issue_id===selected.issue_id);
  return <><div className="issue-pills" aria-label={t("토론 의제")}>{agenda.map((a,i)=><button key={a.issue_id} className={i===issue?'active':''} onClick={()=>transition(()=>setIssue(i))} aria-pressed={i===issue}><span>0{i+1}</span>{a.title}</button>)}</div><section className="issue-intro"><div><span className="eyebrow">{t("KEY QUESTION · 의제 ")}{issue+1}</span><h2>{selected.question || selected.title}</h2>{guide?.core_disagreement && <p>{guide.core_disagreement}</p>}</div><Badge status={issueStatus(data,selected.issue_id)}/></section><div className="round-bar"><span>{t("라운드별 논거")}</span><div>{(data.rounds || []).map((r,i)=><button key={i} className={i===round?'active':''} aria-pressed={i===round} onClick={()=>transition(()=>setRound(i))}>Round {r.round || i+1}</button>)}</div></div><div className="comparison">{['bull','bear'].map(side=><Argument key={side} side={side} turn={r?.[`${side}_response`]?.issues?.find(x=>x.issue_id===selected.issue_id)} fallback={selected[`${side}_claim`]}/>)}</div>{r?.moderator_review?.issue_reviews?.find(x=>x.issue_id===selected.issue_id)?.assessment && <section className="moderator"><span className="eyebrow">{t("진행자 검토 · ROUND ")}{round+1}</span><Text>{r.moderator_review.issue_reviews.find(x=>x.issue_id===selected.issue_id).assessment}</Text></section>}</>;
}
function Sources({data}) {
  const {t,locale}=useLanguage();
  const sources=usedSources(data);
  const types={broker_report:t('증권사 리포트'),financial_data:t('재무 데이터'),news:t('뉴스'),official:t('공식 자료'),dart:t('공시'),report:t('보고서'),blog:t('블로그'),youtube:t('영상'),rag:t('문서 검색'),unknown:t('유형 미상')};
  return <section className="sources"><span className="eyebrow">SOURCES & EVIDENCE</span><h2>{t("토론에 사용한 근거 ")}<small>{sources.length}{t("개 자료")}</small></h2><p className="muted">{t("저장된 토론의 인용 기록을 기준으로 모았습니다. 인용 대조는 주장 자체의 사실 검증을 뜻하지 않습니다.")}</p>{sources.length===0?<p className="paper">{t("이 분석에는 구조화된 출처 기록이 없습니다. 분석·반론 원문에서 근거를 확인해 주세요.")}</p>:sources.map((source,index)=>{const href=safeUrl(source.source_url || source.source_page_url);return <article className="source-item" key={index}><div className="source-heading"><span className="source-type">{types[source.source_type] || source.source_type || t('유형 미상')}</span><span className="metadata">{source.published_at || t('발행일 미상')}</span></div><h3>{source.title || source.source_id || t('제목 없는 자료')}</h3><div className="source-uses">{source.uses.map(use=><span key={use}>{locale==='en'?use.replace('의제 미상','Issue not recorded'):use}</span>)}</div>{href && <a href={href} target="_blank" rel="noreferrer">{t("출처 원문 열기 ↗")}</a>}<details className="source-quotes"><summary>{t("사용한 인용 ")}{source.quotes.length}{t("개 보기")}</summary>{source.quotes.map((quote,i)=><blockquote key={i}>{quote}</blockquote>)}</details></article>})}</section>;
}

export function Detail({data,onBack}) {
  const {t}=useLanguage();
  const [tab,setTab]=useState('debate');
  return <><button className="back" onClick={onBack}>{t("← 전체 리서치")}</button><header className="detail-heading"><div><span className="eyebrow">{data.financial_data?.ticker || 'RESEARCH SESSION'} · {t(dateLabel(data.created_at))}</span><h1>{data.company_name}<span className="light">{t(" 투자 토론")}</span></h1><p className="muted">{t("저장된 분석 · 가격 기준일 ")}{t(dateLabel(data.financial_data?.price_date))}</p></div><span className="read-only">{t("● 결과 열람 전용")}</span></header><div className="detail-metrics"><div><span>{t("토론 의제")}</span><strong>{data.agenda?.length || 0}<small>{t("개")}</small></strong></div><div><span>{t("진행 라운드")}</span><strong>{data.rounds?.length || 0}<small>{t("회")}</small></strong></div><div><span>{t("추가 확인 쟁점")}</span><strong>{(data.agenda||[]).filter(a=>issueStatus(data,a.issue_id)!=='RESOLVED').length}<small>{t("개")}</small></strong></div><div><span>{t("판단 방식")}</span><strong className="word">{t("근거 기반 비교")}</strong></div></div><nav className="tabs" aria-label={t("분석 보기")}>{[['debate',t('토론 탐색')],['summary',t('최종 정리')],['sources',t('사용한 근거')],['original',t('분석·반론 원문')]].map(([id,label])=><button key={id} onClick={()=>transition(()=>setTab(id))} aria-pressed={tab===id} className={tab===id?'active':''}>{label}</button>)}</nav>{tab==='debate'?<Debate data={data}/>:tab==='summary'?<Summary data={data}/>:tab==='sources'?<Sources data={data}/>:<div className="comparison"><article className="paper"><span className="eyebrow">BULL</span><h2>{t("상승 논거")}</h2><Text>{data.bull_analysis}</Text></article><article className="paper"><span className="eyebrow">BEAR</span><h2>{t("하락 논거")}</h2><Text>{data.bear_analysis}</Text></article></div>}</>;
}
export class ResultBoundary extends React.Component {
  static contextType=LanguageContext;
  state={failed:false};
  static getDerivedStateFromError(){return {failed:true};}
  render(){
    const {t}=this.context;
    if(this.state.failed)return <section className="paper" role="alert"><h2>{t("이 분석을 표시하지 못했습니다")}</h2><p>{t("결과 형식을 확인한 뒤 다시 열어 주세요.")}</p><button className="primary" onClick={this.props.onBack}>{t("리서치 목록으로 돌아가기")}</button></section>;
    return this.props.children;
  }
}
