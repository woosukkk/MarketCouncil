# MarketCouncil 근거 품질 보완·검증

점검일: 2026-10-15

## 결론

금융 수치가 인용 후보에서 빠지는 원인을 수정하고, 토론 발언의 숫자·날짜 검사를 연결했다. 가격 통화와 재무 통화도 분리했다. 배포, 운영 DB 변경, 실제 AI 재생성·공식 게시를 실행하지 않았다.

**Python 120개 + 별도 함수형 검사 7개 + 웹 33개가 통과했다.** 기존 미커밋 작업을 제외한 Git 인덱스의 코드만 별도 폴더에 추출해 같은 검사를 통과했다.

## 1. 확인한 원인과 수정

| 문제 | 수정 | 주요 파일 |
|---|---|---|
| 금융 JSON의 앞쪽부터 인용 16개를 선택해 뒤의 FCF·주식 수 변화율이 빠짐 | 지표별로 값·단위·기간·제공된 계산 기준을 묶어 인용 생성. 연간 입력에도 금액/주식 단위를 표시. 전체 금융 원본은 기존 financial_data에 보존 | tools/evidence_catalog.py, test_financial_evidence.py |
| 주가 통화를 매출·FCF에도 붙일 수 있음 | 제공자의 가격 통화와 재무 통화를 독립 조회. 확인 불가를 추정하지 않음. 새 입력의 통화가 다르거나 미확인이면 FCF 수익률 계산 보류 | tools/financial_data.py, tools/quality_valuation.py, test_financial_currency.py |
| 인용 ID가 맞아도 발언의 실제 숫자가 인용에 없을 수 있음 | claim·response·warrant·example_or_data의 명시적 금융 숫자를 선택 인용과 대조. 부족한 근거를 missing_evidence에 전달 | tools/citation_quality.py, agents/analysis_debate_agent.py |
| 지수 표기의 일부를 음수 퍼센트로 잘못 읽을 수 있음 | 지수 표기를 하나의 수로 파싱. 1e-05%와 0.00001%를 같게 읽고 -5%와 구분 | tools/citation_quality.py, tests/test_citation_quality.py |
| 시간대 경계·잘못된 날짜 문자열 처리 | 명시적 ISO/DART 날짜와 시간대가 있는 ISO 시각만 허용. 시각은 한국 날짜로 변환. 임의 접미사/시간대 없는 시각은 날짜 미상 | tools/evidence_dates.py, app/regime_workflow.py, test_evidence_dates.py |
| 과거 전망이 현재 단기 판단으로 승격될 수 있음 | 분석 기준일을 양측·중재자·요약에 전달. 미래 인용은 사용 목록에서 제외. 오래된 전망을 단기에 쓰는 경우 검토 경고 | agents/analysis_debate_agent.py, analysis_debate_prompt.py, moderator_prompt.py |
| 수정 전 발언을 체크포인트에서 재사용할 수 있음 | 카탈로그·품질 검사·날짜·금융 코드도 실행 버전 서명에 포함 | app/recoverable_debate_workflow.py |

기존 구버전 금융 입력에 통화 필드가 아예 없으면 계산 호환을 유지하면서 통화 미검증 가정을 남긴다. 새 수집 경로에서는 확인되지 않은 통화를 추정하거나 환산하지 않는다.

## 2. 검사의 의미

- **identity_status**: 출처·인용 ID와 원문 연결 확인. 주장 자체의 진위가 아니다.
- **numeric_status**: 명시적 수치·단위가 인용에 있는지 확인. 표시 정밀도에 따른 반올림을 허용한다. 지표·방향·기간·인과관계가 같다는 뜻은 아니다.
- **semantic_status**: 항상 `not_evaluated`. 이번 코드에 의미 검증 완료 판정은 없다.
- 날짜 미상은 경고로 남기고, 기준일 이후로 확인되는 인용은 제거한다. 날짜 미상 자료가 과거에 존재했다고 보증하지 않는다.
- `stale_forecast`는 **90일 초과 자료 + 단기 표현 + 인용의 전망 표현**을 조합한 규칙이다. 잘못된 주장 확정이나 자료의 유효기간 판정이 아니다. 오래된 역사적 사실 자체는 차단하지 않는다.
- 상대방 주장을 옮긴 target_claim과 가정·양보 필드는 수치 검사에서 제외한다. 현재 숫자 파서는 KRW/USD·원/달러·퍼센트·주식 수·배수·큰 수 단위를 중심으로 지원한다. 모든 언어·통화를 검사하지 않는다.

참가자와 중재자 프롬프트는 지표·기간이 맞는 인용을 요구하고, 근거 없는 수치를 합의된 사실로 올리지 않도록 보완했다. 실제 모델이 이를 얼마나 잘 따르는지는 별도 생성 평가가 필요하다.

## 3. 저장된 삼성전자 결과의 오프라인 점검

대상: 로컬 `analysis_debate_20261015_094303.json` 한 개. 저장 파일을 수정·업로드하거나 외부 AI에 재전송하지 않았다.

| 항목 | 결과 |
|---|---:|
| 발언별 쟁점 | 18개 |
| 인용 연결 matched | 18개 |
| 의미 검증 not_evaluated | 18개 |
| 숫자 확인 필요 needs_review | 12개 |
| 숫자 존재 values_present / 해당 숫자 없음 not_applicable | 3개 / 3개 |
| 오래된 전망 검토 경고 | 6개 |
| 미래 자료 / 날짜 미상 경고 | 0개 / 0개 |

12개와 6개는 서로 겹칠 수 있다. 숫자 경고는 전체 검사항목의 수치가 선택한 인용 안에 없다는 뜻이며, 원본 전체에도 없거나 거짓이라는 뜻이 아니다. 설명란까지 검사하면서 claim만 검사할 때의 숫자 검토 대상 6개에서 12개로 늘었다. 잘못된 주장이나 할루시네이션 비율로 계산하지 않는다.

같은 금융 원본으로 카탈로그만 새로 구성하면 FIN 인용 16개가 지표별 13개로 바뀐다. 기존 후보에서 빠졌던 normalized_fcf·fcf_yield·dilution_rate가 각각 포함된다. 이 옛 결과에는 재무 통화가 없으므로 새 인용도 통화 미제공으로 표시한다. 기존 게시물이나 선택 인용이 자동으로 교체되는 것은 아니다.

### 규칙 검사 시간

같은 18개 쟁점 전체를 3회 예열 후 100회 검사했다.

- 중앙값: **2.5613ms**
- p95: **5.7573ms**
- 측정 범위: 메모리에 읽은 결과의 규칙 검사만. 파일 읽기, 자료 수집, 모델 생성, 전체 프로그램 실행 시간은 제외.
- 같은 결과를 반복한 로컬 측정으로, 동시 사용자 처리량이나 일반 서비스 지연을 뜻하지 않는다.

상세 집계: `C:/MarketCouncil/results/metrics/citation-quality-20261015.json` — 로컬 Git 제외 파일. 원문·발언을 담지 않은 집계다.

## 4. 검증과 재현

- Python 회귀 **120개**: 기존 기업 검색·시점 검색·자동 실행·복구·출처·결과 형식 검사 및 새 날짜·금융·인용 검사 포함.
- 별도 함수형 검사 **7개**: test_evidence_catalog 4개와 test_regime_workflow 3개를 명시적으로 실행. unittest에서 수집되지 않는 함수를 통과 수에 잘못 포함하지 않았다.
- 웹 단위 **33개**: 기존 결과 열람·업로드·목록·형식·성능 기록 계약 검사.
- 실제 LangGraph 2라운드에서 모델 응답만 모의 처리하여 기준일과 검사 결과가 양측·검토·요약으로 전달됨을 확인.
- 기존 미커밋 파일을 제외한 추출 소스에서 위 127개 Python 검사와 33개 웹 검사를 다시 통과.
- 새 날짜 기본형 테스트, 시간대 경계, 적합한 연간 금액·주식 수 인용, 반올림·지수 표기, 미래 인용의 토론 연장 차단 포함.

주요 명령:

```text
venv/Scripts/python.exe -B -m unittest test_desktop_lookup test_financial_growth test_retrieval_cutoff test_daily_official test_analysis_recovery tests.test_debate_termination test_performance_reports test_result_export test_publish_results test_result_validation test_desktop test_desktop_official test_company_lookup tests.test_quality_valuation test_regime_workflow test_source_collector_fallback test_evidence_dates test_financial_currency test_financial_evidence tests.test_citation_quality tests.test_debate_quality -q
node --test frontend/src/*.test.js
```

첫 명령의 test_regime_workflow는 함수형 검사를 자동 수집하지 않는다. 별도 7개는 두 모듈의 test_ 함수를 unittest.FunctionTestCase로 감싸 실행했다. 테스트에는 모의 API 응답과 더미 키를 사용했다.

## 5. 적용 범위와 남은 검증

- **배포·운영 DB·공개 결과·일일 자동 작업 실행을 변경하지 않았다.** 현재 배포 사이트에는 이번 수정이 아직 적용되지 않는다. 로컬 자동 작업은 다음 실행부터 소스 변경의 영향을 받는다.
- 실행 버전이 다른 기존 체크포인트는 재사용을 거부한다. 파일을 자동 삭제하거나 유료 분석을 재시작하지 않았다.
- 금융 통화 확인에는 다음 실행 시 제공자 get_info 요청이 추가될 수 있다. 실제 제공자 지연·성공률과 전체 분석 시간은 이번에 측정하지 않았다.
- 날짜 검사는 한국 날짜 단위다. 같은 날 안의 발표 시각은 구분하지 않는다. 미래 인용은 제거하지만 원본 카탈로그·최초 분석 등 LLM 입력 전체의 미래 정보 제거까지 구현한 것은 아니므로 과거 시점 백테스트를 보증하지 않는다.
- 실제 AI 재생성, 독립 전문가 평가, 전체 문장 의미·계산·기간 정합성 평가는 남아 있다. 규칙 경고만으로 결과 공개를 자동 차단하지는 않는다.
- 다음 품질 단계는 고정 질문·정답 근거를 확대하고 같은 입력으로 생성 결과를 비교하는 것이다. 기존 검색 성능의 12문항 파일럿 수치를 이번 생성 품질 점수로 재사용하지 않는다.
- UX·북마크·공식 비공개 전환·운영 DB 검증 등 기존 감사의 보류 항목은 이 수정으로 해결됐다고 표시하지 않는다.
