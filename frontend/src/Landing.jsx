import React, {useEffect, useState} from 'react';
import {dateLabel} from './data.js';

// Remember revealed sections across home/service navigation until page reload.
const revealedSections = new Set();

export default function Landing({navigate}) {
  const [sample,setSample]=useState(null);
  useEffect(()=>{
    const abort=new AbortController();
    fetch('/data/index.json',{signal:abort.signal}).then(r=>{if(!r.ok)throw Error();return r.json()})
      .then(rows=>{if(!rows[0])throw Error();return fetch(`/data/${rows[0].id}.json`,{signal:abort.signal})})
      .then(r=>{if(!r.ok)throw Error();return r.json()}).then(setSample).catch(()=>{});
    return()=>abort.abort();
  },[]);
  useEffect(()=>{
    if(matchMedia('(prefers-reduced-motion: reduce)').matches)return;
    const observer=new IntersectionObserver(entries=>entries.forEach(e=>{
      if(!e.isIntersecting)return;
      e.target.classList.add('in-view');
      revealedSections.add(e.target.dataset.revealKey);
      observer.unobserve(e.target);
    }),{threshold:0.06});
    document.querySelectorAll('.reveal').forEach((el,index)=>{
      el.dataset.revealKey=String(index);
      if(revealedSections.has(String(index))) { el.classList.add('in-view'); return; }
      el.classList.add('observed');
      observer.observe(el);
    });
    return()=>observer.disconnect();
  },[]);
  const link=e=>{if(e.button===0&&!e.metaKey&&!e.ctrlKey&&!e.shiftKey&&!e.altKey){e.preventDefault();navigate('/app')}};
  const issue=sample?.agenda?.[0];
  return <div className="landing">
    <header className="landing-nav"><a className="landing-brand" href="/">MarketCouncil<span>↗</span></a><nav aria-label="홈페이지 메뉴"><a href="#approach">분석 방식</a><a href="#preview">분석 예시</a><a className="nav-start" href="/app" onClick={link}>서비스 시작하기 <span>↗</span></a></nav></header>
    <main>
      <section className="landing-hero reveal"><div className="landing-kicker"><span/> INVESTMENT RESEARCH, IN PERSPECTIVE</div><h1>좋은 판단은,<br/><span>다른 관점</span>에서 시작됩니다.</h1><p>하나의 기업을 둘러싼 상승과 하락의 가설.<br/>서로 다른 주장과 그 근거를 한곳에서 읽어보세요.</p><div className="landing-actions"><a className="landing-cta" href="/app" onClick={link}>리서치 살펴보기 <span>↗</span></a><a className="text-link" href="#preview">분석 예시 보기 <span>↓</span></a></div><div className="hero-footnote">근거를 읽고 · 가설을 비교하고 · 남은 질문을 확인하세요</div></section>
      <section id="preview" className="product-stage reveal" aria-label="저장된 분석 예시"><div className="preview-window"><div className="preview-toolbar"><span className="preview-logo">M<span>c</span></span><strong>MarketCouncil</strong><span className="example-tag">실제 저장된 분석 예시</span><span className="preview-date">{dateLabel(sample?.created_at)}</span></div><div className="preview-layout"><aside className="preview-sidebar"><span>WORKSPACE</span><div className="selected">▦ 리서치 라이브러리</div><div>↗ 상승 가설</div><div>↘ 하락 가설</div><div>≡ 근거와 출처</div><small>READ. QUESTION.<br/>COMPARE.</small></aside><div className="preview-content"><div className="preview-title"><div><span className="landing-kicker">RESEARCH OVERVIEW</span><h2>{sample?.company_name || '투자 토론'} <span>분석 리포트</span></h2></div><span className="example-status">저장된 결과</span></div>{sample ? <><div className="preview-stats"><div><small>토론 의제</small><strong>{sample.agenda?.length || 0}<span>개</span></strong></div><div><small>토론 라운드</small><strong>{sample.rounds?.length || 0}<span>회</span></strong></div><div><small>분석 기준</small><strong className="preview-stat-text">근거 비교</strong></div></div><div className="preview-question"><span>핵심 질문</span><h3>{issue?.question || issue?.title || '어떤 근거가 투자 가설을 뒷받침하는가?'}</h3></div><div className="preview-arguments"><article><span className="bull-text">↗ BULL · 상승 가설</span><p>{issue?.bull_claim || '기록된 상승 주장이 없습니다.'}</p><small>주장을 지지하는 근거 살펴보기</small></article><article><span className="bear-text">↘ BEAR · 하락 가설</span><p>{issue?.bear_claim || '기록된 하락 주장이 없습니다.'}</p><small>반대 근거와 위험 요인 살펴보기</small></article></div></>:<div className="preview-placeholder">분석 예시는 서비스에서 확인할 수 있습니다.</div>}<a className="preview-open" href="/app" onClick={link}>전체 토론과 인용 원문 읽기 <span>→</span></a></div></div></div><p className="example-caption">실시간 시세가 아닌 분석 시점의 기록입니다. 예시는 내용을 축약해 보여줍니다.</p></section>
      <section id="approach" className="approach reveal"><div className="section-caption">LESS NOISE. MORE REASONING.</div><h2>결론만 보지 마세요.<br/><span>그 판단에 이른 과정을 보세요.</span></h2><div className="approach-grid"><article><span className="step-number">01 / COMPARE</span><h3>두 관점을 나란히.</h3><p>Bull과 Bear가 같은 쟁점에 어떻게 답하는지 비교하세요. 가설의 성립 조건과 반대 논거까지 함께 읽습니다.</p></article><article><span className="step-number">02 / VERIFY</span><h3>주장 뒤의 근거까지.</h3><p>인용문을 펼쳐보고 출처 원문으로 이동하세요. 인용 대조 여부와 가설의 타당성을 구분해 확인합니다.</p></article><article><span className="step-number">03 / FOLLOW THROUGH</span><h3>남은 질문을 명확하게.</h3><p>양측이 합의한 사실, 해소되지 않은 쟁점, 다음에 확인할 자료를 최종 정리에서 살펴보세요.</p></article></div></section>
      <section className="closing reveal"><span className="section-caption">YOUR NEXT PERSPECTIVE</span><h2>확신에 앞서,<br/>근거를 마주할 시간.</h2><a className="landing-cta" href="/app" onClick={link}>서비스 시작하기 <span>↗</span></a><p>현재는 저장된 분석 결과를 열람하는 서비스입니다.</p></section>
    </main><footer className="landing-footer"><a className="landing-brand" href="/">MarketCouncil<span>↗</span></a><p>AI가 생성한 분석 기록입니다. 투자 판단의 정확성을 보장하지 않습니다.</p><a href="/app" onClick={link}>리서치 라이브러리 ↗</a></footer>
  </div>;
}
