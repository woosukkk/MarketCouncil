import React from 'react';
import profiles from './companyProfiles.json';
import {useLanguage} from './Language.jsx';
import {withLanguage} from './language.js';

const normalize=value=>String(value||'').replace(/\s/g,'').toLowerCase();
export function matchesCompany(row,ticker){
 if(!ticker)return true;
 const profile=profiles.find(company=>company.ticker===ticker);
 return !!profile&&(row.ticker===ticker||profile.aliases.some(alias=>normalize(alias)===normalize(row.company_name)));
}

export default function CompanyResearch({rows,selected,onSelect}){
 const {t,locale}=useLanguage();
 return <section className="company-research" aria-labelledby="company-research-title">
  <div className="section-heading"><div><span className="eyebrow">COMPANY RESEARCH</span><h2 id="company-research-title">{t('기업별 리서치')}</h2></div><button className="company-reset" onClick={()=>onSelect('')} aria-pressed={!selected}>{t('전체 기업')}</button></div>
  <p>{t('기업을 선택해 공개된 분석을 살펴보세요. 새 토론은 PC 프로그램에서 실행하고 원하는 결과를 공유할 수 있습니다.')}</p>
  <div className="company-directory">{profiles.map(profile=><button key={profile.ticker} className="company-choice" aria-pressed={selected===profile.ticker} onClick={()=>onSelect(selected===profile.ticker?'':profile.ticker)}>
   <span className="company-market">{profile.market==='kr'?'KOREA':'UNITED STATES'}</span><strong>{profile.company_name}</strong><span>{profile.ticker}</span><small>{rows===null?t('목록 불러오는 중'):t('{0}개의 공개 분석',{0:rows.filter(row=>matchesCompany(row,profile.ticker)).length})}</small>
  </button>)}</div>
  <div className="company-research-note"><p>{t('PC 분석은 공시와 실적 발표 자료를 먼저 확인합니다. 자료가 부족한 기업은 분석 시작 전에 안내합니다.')}</p><a href={withLanguage('/download',locale)}>{t('내 PC에서 분석 준비하기 →')}</a></div>
 </section>;
}
