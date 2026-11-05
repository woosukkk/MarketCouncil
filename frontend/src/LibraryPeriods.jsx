import React from 'react';
import {useLanguage} from './Language.jsx';
import {groupLibraryPeriods} from './libraryPeriods.js';
import './libraryPeriods.css';

export default function LibraryPeriods({rows, searching, renderCard}) {
  const {t, locale} = useLanguage();
  const grid = items => <div className="session-grid">{items.map(renderCard)}</div>;
  if (searching) return grid(rows);
  const {recent, older} = groupLibraryPeriods(rows);
  const label = group => {
    const values = {0:group.year, 1:group.period};
    if (group.kind === 'month') {
      return new Intl.DateTimeFormat(locale === 'en' ? 'en-US' : 'ko-KR', {year:'numeric', month:'long', timeZone:'UTC'})
        .format(new Date(`${group.year}-${String(group.period).padStart(2, '0')}-01T00:00:00Z`));
    }
    if (group.kind === 'quarter') return t('{0}년 {1}분기', values);
    if (group.kind === 'half') return t(group.period === 1 ? '{0}년 상반기' : '{0}년 하반기', values);
    if (group.kind === 'year') return t('{0}년', values);
    return t('날짜 미상');
  };
  return <>
    {!!recent.length && <section className="library-periods">
      <h3>{t('최근 30일')}</h3>
      {grid(recent)}
    </section>}
    <section className="library-periods" aria-label={t('지난 분석')}>
      <h3>{t('지난 분석')}</h3>
      {!older.length && <p className="muted">{t('30일 이상 지난 기록은 여기에 기간별로 모입니다.')}</p>}
      {older.map(group => <details className="library-period" key={group.id}>
        <summary><strong>{label(group)}</strong><small>{t('분석 {0}건', {0:group.rows.length})}</small></summary>
        {grid(group.rows)}
      </details>)}
    </section>
  </>;
}
