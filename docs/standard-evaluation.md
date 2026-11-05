# 공통 평가 기준과 운영 관측

## 무엇을 비교하는가

화면은 기존 웹 관리자 페이지와 로컬 Streamlit을 사용한다. 지표는 표시 도구와 별개다. 하나의 종합 AI 점수를 만들지 않는다.

| 대상 | 방법 | 해석의 한계 |
| --- | --- | --- |
| 검색 | 기존 고정 정답 ID 기반 Recall@k, Precision@k, MRR | 정답 문서 선정과 청크 단위가 같아야 비교 가능 |
| 답변·문맥 | Ragas Faithfulness, Context Precision, Context Recall, Factual Correctness | 모델 판정이며 판정 모델·참조 답·설정에 의존 |
| 금융 수치 추론 | FinQA 같은 공개 데이터셋 | 국내 공시·시계열 누수·토론 품질 전체를 대표하지 않음 |
| 웹 페이지 | Google PageSpeed Insights / Lighthouse | 실험실 측정과 실제 방문자 집계가 다르며 AI 품질과 별개 |
| 실행 | 기존 단계 시간·API 토큰·관측 비용 | 업로드된 실행만 관측하며 토큰 비용 추정은 계정 청구액이 아님 |

공식 정의: [Ragas metrics](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/), [PageSpeed API](https://developers.google.com/speed/docs/insights/v5/get-started), [FinQA](https://github.com/czyssrs/FinQA), [Langfuse evaluations](https://langfuse.com/docs/evaluation/core-concepts).

## Ragas 결과 가져오기

Ragas는 별도 평가 환경에서 실행한다. 현재 구현은 이미 계산한 사례별 점수를 가져오는 변환기이며 Ragas 실행이나 외부 서비스 연동을 자동 수행하지 않는다. 사용자 요청으로 실제 유료 판정·벤치마크·전체 회귀 실행은 보류했다.

1. 원문과 정답을 로컬에 보관한다. 기업·문서·기준일로 분리한 고정 데이터셋을 만들고 사람 검수 범위를 표시한다. 전체 서비스 정확도로 일반화하지 않는다.
2. Ragas에서 사례별 점수를 계산한 CSV를 준비한다. 열 이름은 `case_id,faithfulness,context_precision,context_recall,factual_correctness`이다. 사용 중인 버전의 메트릭 출력명을 확인해 이 이름으로 내보낸다. 실행하지 않은 지표와 실패/NaN 결과는 빈 칸으로 남긴다. 유효 사례가 하나도 없는 파일은 거절한다.
3. 설정 JSON을 준비한다. 모든 문자열은 120자 이하 영문 식별자다. 원문·API 키·사용자 이메일은 넣지 않는다.

```json
{
  "framework_version": "REPLACE_WITH_INSTALLED_RAGAS_VERSION",
  "dataset_name": "REPLACE_WITH_DATASET_ID",
  "dataset_version": "REPLACE_WITH_DATASET_VERSION",
  "dataset_hash": "REPLACE_WITH_REAL_64_HEX_SHA256",
  "evaluator_model": "REPLACE_WITH_JUDGE_MODEL",
  "reference_origin": "human",
  "metric_config_hash": "REPLACE_WITH_REAL_64_HEX_SHA256"
}
```

`dataset_hash`는 실제 평가 입력 전체의 SHA-256, `metric_config_hash`는 지표 모드·판정 프롬프트·모델 옵션·온도·시드 등 재현에 필요한 설정을 담은 로컬 JSON의 SHA-256이다. `reference_origin`은 `human`, `mixed`, `synthetic` 중 하나다. 설정이나 평가 대상이 달라지면 같은 실험으로 비교하지 않는다. 이 메타데이터는 사용자 선언이며 별도 실행 증명은 아니다.

```powershell
python -m tools.external_evaluation scores.csv --manifest manifest.json --output ragas-report.json
```

출력에는 해시화한 사례 ID, 지표별 점수·유효 수, 버전·데이터셋·판정 모델 식별자만 남는다. 입력 CSV의 질문·원문 열은 읽더라도 출력하지 않는다. 점수는 [0,1] 범위를 검사하고 사례 ID 중복·위조 집계·무한대 값을 거절한다. 기존 출력 파일을 덮어쓰지 않는다. 기록 시각은 변환 시각이며 원래 평가 실행 시각을 소급 추정하지 않는다.

웹의 관리자 → 공통 평가 기준 → 가져오기를 통해 JSON을 저장한다. 기존 `admin_reports` 운영자 전용 권한을 사용하며 DB 권한 변경은 없다. 평균의 분모는 지표별 유효 사례 수이며 누락 점수를 0으로 채우지 않는다. 반입한 점수가 실제 Ragas 실행 결과인지 독립 인증하는 기능은 없다.

## 로컬 Streamlit

프로젝트 가상환경의 Streamlit을 사용한다. 원래 분석 UI와 별도 프로세스이며 공개 서버로 올리지 않는다.

```powershell
.\venv\Scripts\python.exe -m streamlit run tools/monitoring_dashboard.py --server.address 127.0.0.1
```

관리자용 Ragas JSON 또는 기존 `monitoring`의 `analysis`/`web_lighthouse` JSON을 선택한다. 파일당 1MB, 최대 20개다. 질문·원문·키를 표시하거나 업로드하지 않으며 DB와 외부 평가 API를 호출하지 않는다. 성능 기록의 정해진 숫자 열만 표시하고 Ragas 결과는 웹과 동일한 계약으로 재계산·검사한다. 배포 EXE에는 Streamlit을 포함하지 않는다.

## 외부 사이트

관리자 화면에서 공개 페이지를 Google PageSpeed Insights로 열 수 있다. Langfuse는 실험·데이터셋·판정 기록 관리용 선택지로 링크를 제공한다. 별도 계정이 없으므로 자동 API 업로드나 추적 수집은 연결하지 않았다. Ragas는 평가 라이브러리, Langfuse는 기록 도구이며 어느 쪽도 독립적인 금융 전문가 인증이 아니다.

검증 재개 시에는 프레임워크 버전 고정 → 사람 정답 검수 → 미사용 평가 세트 분리 → 기업별/시점별 누수 검사 → 반복 판정과 편차 기록 → 기존 버전 비교 순으로 진행한다. 개발용 합성 사례 점수를 실제 서비스 정확도로 게시하지 않는다.
