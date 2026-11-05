"""Local-only viewer. No database credentials or model calls."""
import json
import math
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.external_evaluation import METRICS, validate_report

st.set_page_config(page_title='MarketCouncil monitoring', layout='wide')
st.title('MarketCouncil · 로컬 모니터링')
st.caption('기존 기록을 읽기만 합니다. 외부 전송·분석·벤치마크 실행은 하지 않습니다.')
files = st.file_uploader('관리자용 성능 또는 Ragas JSON', type=['json'], accept_multiple_files=True, max_upload_size=1)
if len(files) > 20:
    st.error('최대 20개 기록을 선택하세요.')
    st.stop()
if not files:
    st.info('측정 기록을 선택하세요. 미측정 값을 추정하거나 예시 점수로 채우지 않습니다.')
for index, file in enumerate(files):
    try:
        raw = json.loads(file.getvalue())
        if not isinstance(raw, dict):
            raise ValueError()
        with st.container(border=True):
            if raw.get('scope') == 'external_rag':
                report = validate_report(raw)
                st.subheader('Ragas · 외부 평가 기록')
                st.caption(f"{report['recorded_at']} · Ragas {report['version']} · {report['settings']['evaluator_model']}")
                st.caption(f"Dataset SHA-256: {report['dataset_hash']} · Config SHA-256: {report['settings']['metric_config_hash']}")
                st.caption(f"Reference: {report['settings']['reference_origin']} · {report['settings']['dataset_name']} / {report['settings']['dataset_version']}")
                chart = []
                with st.container(horizontal=True):
                    for key in METRICS:
                        value = report['metrics'][key]
                        st.metric(key, '미평가' if value is None else f'{value:.1%}')
                        if value is not None:
                            chart.append({'metric': key, 'score': value})
                if chart:
                    st.bar_chart(chart, x='metric', y='score')
                st.caption('모델 판정 추정값입니다. 데이터셋·판정 모델·설정이 같은 기록끼리 비교하세요. 누락 점수는 0이 아닙니다.')
                st.dataframe(report['cases'], hide_index=True)
            elif raw.get('schema_version') == 1 and raw.get('kind') == 'monitoring' and raw.get('scope') in ('analysis', 'web_lighthouse') and raw.get('status') in ('success', 'failed'):
                st.subheader('분석 실행' if raw['scope'] == 'analysis' else 'Lighthouse 웹 성능')
                st.caption('API 관측 비용은 계정 청구액이 아닙니다. 웹 성능은 AI 품질과 별개입니다.')
                allowed = ('duration_ms', 'cpu_ms', 'performance_score', 'fcp_ms', 'lcp_ms', 'tbt_ms', 'cls', 'speed_index_ms')
                values = raw.get('metrics')
                if not isinstance(values, dict):
                    raise ValueError()
                metrics = []
                for key in allowed:
                    if key in values:
                        value = values[key]
                        if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
                            raise ValueError()
                        metrics.append({'metric': key, 'value': value})
                if not metrics:
                    raise ValueError()
                st.dataframe(metrics, hide_index=True)
                st.caption('완료' if raw['status'] == 'success' else '실패')
            else:
                raise ValueError()
    except (ValueError, TypeError, KeyError, UnicodeError):
        st.error(f'기록 {index + 1}: 지원하는 관리자 JSON 형식과 점수 범위를 확인하세요.')
