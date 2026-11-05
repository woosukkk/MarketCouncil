import React,{useState} from 'react';
import {useLanguage} from './Language.jsx';
import './relations.css';
import {companyRelations,relationNodes,relationsAsOf,relationsFor} from './companyRelations.js';

export default function Relationships({onResearch}){
 const {locale,t}=useLanguage(),[selected,setSelected]=useState('');
 const language=locale==='en'?1:0;
 const label=node=>locale==='en'?(node.en||node.name):node.name;
 const nodes=Object.fromEntries(relationNodes.map(node=>[node.id,node]));
 const visible=relationsFor(selected),active=new Set(visible.flatMap(row=>[row.from,row.to]));
 const kinds={supplier:t('공급망 기록'),integration:t('제품 통합'),development:t('공동 개발')};
 return <section className="account-page relationship-page">
  <span className="eyebrow">{t('로컬 검토용')} · CONNECTED RESEARCH</span><h1>{t('기업 관계와 영향 경로')}</h1>
  <p>{t('공식 출처에서 확인한 연결을 따라 긍정·부정 조건과 추가로 확인할 데이터를 살펴봅니다.')}</p>
  <p className="muted">{t('자료 확인 기준일')} · {relationsAsOf} · {t('발표 당시의 사실이며 현재 계약 존속·공급량·주가 상관관계를 확인한 것은 아닙니다.')}</p>
  <div className="relation-toolbar"><button className="company-reset" aria-pressed={!selected} onClick={()=>setSelected('')}>{t('전체 기업')}</button><span>{t('기업을 누르면 직접 연결된 관계를 표시합니다.')}</span></div>
  <div className="relation-map" aria-label={t('기업 관계도')}>
   <svg viewBox="0 0 1000 480" aria-hidden="true" preserveAspectRatio="none">{companyRelations.map(row=><line key={row.id} x1={nodes[row.from].x*10} y1={nodes[row.from].y*4.8} x2={nodes[row.to].x*10} y2={nodes[row.to].y*4.8} className={visible.includes(row)?row.historical?'historical':'current':'dimmed'}/>)}</svg>
   {relationNodes.map(node=><button key={node.id} style={{left:node.x+'%',top:node.y+'%'}} className={'relation-node'+(selected===node.id?' selected':'')+(!active.has(node.id)?' dimmed':'')} aria-pressed={selected===node.id} onClick={()=>setSelected(selected===node.id?'':node.id)}><strong>{label(node)}</strong><small>{node.reference?t('참조 기업'):node.id}</small></button>)}
  </div>
  <p className="muted">{t('점선은 오래된 기준 자료입니다. 선은 관계 존재를 나타내며 영향의 크기나 주가 방향을 뜻하지 않습니다. NVIDIA는 관계 설명용 참조 기업입니다.')}</p>
  <div className="relation-cards">{visible.map(row=><article key={row.id} className="relation-card">
   <div className="relation-heading"><span className="eyebrow">{kinds[row.type]}</span><span>{row.period}{row.historical?' · '+t('과거 기준 자료'):''}</span></div>
   <h2>{label(nodes[row.from])} ↔ {label(nodes[row.to])}</h2>
   <h3>{t('확인된 발표·기록')}</h3><p>{row.fact[language]}</p>
   <details className="relation-evidence">
    <summary>{t('원문 근거')} · {row.evidence.length}</summary>
    {row.evidence.map(item=><div key={item.url} className="relation-evidence-item">
     <a href={item.url} target="_blank" rel="noreferrer">{item.source} ↗</a>
     <small>{item.locator}</small>
     <blockquote lang="en">{item.excerpt}</blockquote>
     <p>{item.data[language]}</p>
     <p className="muted">{item.limit[language]}</p>
    </div>)}
   </details>
   <div className="relation-scenarios"><div><h3>{t('긍정 조건 · 가설')}</h3><p>{row.upside[language]}</p></div><div><h3>{t('위험 조건 · 가설')}</h3><p>{row.downside[language]}</p></div></div>
   <h3>{t('추가 확인 데이터')}</h3><p>{row.needed[language]}</p>
   <div className="relation-actions">{[row.from,row.to].filter(id=>!nodes[id].reference).map(id=><button key={id} onClick={()=>onResearch(id)}>{label(nodes[id])} · {t('공개 분석 보기')} →</button>)}</div>
  </article>)}</div>
  <p className="muted">{t('영향 경로는 검토용 조건부 가설입니다. 관계가 있다는 이유만으로 수익 증가나 투자 결론을 생성하지 않습니다. 토론 원문과 별도로 관리하는 출처 기반 리서치 지도입니다.')}</p>
 </section>;
}
