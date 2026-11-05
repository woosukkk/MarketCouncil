import React from 'react';
import {useLanguage} from './Language.jsx';
import {metricText} from './adminData.js';
import {externalMetrics} from './externalEvaluation.js';
const docs='https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/';
const definitions={
 faithfulness:['근거 충실도','생성 답변의 주장이 검색 문맥으로 뒷받침되는지 평가합니다. 원문 자체의 진실성을 보증하지는 않습니다.'],
 context_precision:['문맥 정밀도','정답에 유용한 검색 문맥이 상위에 배치됐는지 평가합니다. 기존 ID 기반 Precision@k와 구분합니다.'],
 context_recall:['문맥 재현율','기준 정답의 주장이 검색 문맥에서 얼마나 확인되는지 평가합니다. 기준 정답이 필요합니다.'],
 factual_correctness:['정답 사실 일치','답변의 주장을 기준 정답과 비교합니다. 평가 모드·판정 모델과 정답 품질에 영향을 받습니다.'],
};
export default function StandardEvaluation({reports}){
 const {t,locale}=useLanguage(),latest=reports[0];
 return <section className="standard-evaluation">
  <h2>{t('공통 지표로 보는 평가')}</h2><p>{t('화면 도구와 평가 기준을 분리합니다. Ragas 지표, 고정 정답 기반 검색 평가, Lighthouse 웹 성능을 각각 비교합니다.')}</p>
  <p className="muted">{t('Ragas의 모델 판정은 객관적인 정답이나 금융 예측 정확도를 보증하지 않습니다. 데이터셋·판정 모델·설정이 같은 기록끼리 비교하고 사람 검수로 보완하세요.')}</p>
  <div className="standard-grid">{externalMetrics.map(key=><article className="standard-card" key={key}>
   <span className="eyebrow">RAGAS · {key}</span><h3>{t(definitions[key][0])}</h3><strong className="standard-score">{latest?metricText(latest.metrics[key],true):t('미평가')}</strong><p>{t(definitions[key][1])}</p>
   {latest&&<small>{t('유효 사례')} {latest.metrics[key+'_count']} / {latest.metrics.case_count}</small>}<a href={docs+key+'/'} target="_blank" rel="noreferrer">{t('지표 정의')} ↗</a>
  </article>)}</div>
  <div className="paper"><h3>{t('외부 평가 결과 가져오기')}</h3><p>{t('Ragas에서 계산한 사례별 점수 CSV를 로컬 변환기로 JSON으로 만든 뒤 위의 가져오기로 저장하세요. 질문·답변·원문은 업로드하지 않습니다. 아직 평가를 실행하지 않았습니다.')}</p><code>python -m tools.external_evaluation scores.csv --manifest manifest.json --output ragas-report.json</code><p className="muted">{t('가져온 점수는 사용자가 제공한 측정값입니다. 실제 Ragas 실행 여부를 이 화면이 독립 검증하지 않습니다. 누락된 점수는 0점으로 처리하지 않습니다.')}</p></div>
  <h3>{t('외부 도구와 공개 기준')}</h3><div className="external-tools">
   <a href="https://pagespeed.web.dev/analysis?url=https%3A%2F%2Ffrontend-six-pi-h5i7tztups.vercel.app%2Fapp" target="_blank" rel="noreferrer">Google PageSpeed Insights ↗<small>{t('공개 웹 페이지의 Lighthouse·방문자 지표. AI 답변 품질과 별개입니다.')}</small></a>
   <a href="https://langfuse.com/docs/evaluation/core-concepts" target="_blank" rel="noreferrer">Langfuse ↗<small>{t('실험·데이터셋·사람 검수 관리 도구. 별도 계정이 필요하며 자동 전송은 연결하지 않았습니다.')}</small></a>
   <a href="https://github.com/czyssrs/FinQA" target="_blank" rel="noreferrer">FinQA ↗<small>{t('금융 수치 추론용 공개 데이터셋. 국내 공시와 토론 전체의 품질을 대표하지 않습니다.')}</small></a>
  </div>
  <h3>{t('Streamlit 로컬 대시보드')}</h3><p>{t('같은 성능·Ragas JSON을 PC에서 볼 수 있습니다. 로컬 읽기 전용이며 서버·계정 연결 없이 실행합니다.')}</p><code>python -m streamlit run tools/monitoring_dashboard.py --server.address 127.0.0.1</code>
  <p className="muted">{t('Streamlit은 표시 도구입니다. 측정 방법이나 점수를 바꾸지 않으며, 실제 측정은 별도 실행해야 합니다.')}</p>
  {!!reports.length&&<><h3>{t('외부 평가 기록')}</h3><div className="admin-table"><table><thead><tr>{['측정 시각','평가 조건','기준 정답 출처','유효 사례'].map(key=><th key={key}>{t(key)}</th>)}</tr></thead><tbody>{reports.map(row=><tr key={row.id}><td>{new Date(row.recorded_at).toLocaleString(locale==='en'?'en-US':'ko-KR')}</td><td>Ragas {row.version} · {row.settings.evaluator_model}<br/>{row.settings.dataset_name} · {row.settings.dataset_version}<br/><small>{row.dataset_hash.slice(0,12)} · config {row.settings.metric_config_hash.slice(0,12)}</small></td><td>{row.settings.reference_origin}</td><td>{externalMetrics.map(key=><div key={key}>{key}: {metricText(row.metrics[key],true)} ({row.metrics[key+'_count']}/{row.metrics.case_count})</div>)}</td></tr>)}</tbody></table></div></>}
 </section>;
}
