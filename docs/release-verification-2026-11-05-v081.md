# 2026-11-05 발행사 원문·기업 관계·평가 화면 배포 기록

## 실제 배포

| 대상 | 버전 | 실제 소스 | 주소 |
| --- | --- | --- | --- |
| Windows | desktop-v0.8.1 | ac19ff88d88578d13e66fbaa17eb248eaef160eb | https://github.com/woosukkk/MarketCouncil/releases/tag/desktop-v0.8.1 |
| Web | web-v0.15.0 | 3c9200fd2c1b927f673e9c436cc9e7cc0da36a76 | https://frontend-bdtixb4e5-woosukk.vercel.app |

운영 주소는 https://frontend-six-pi-h5i7tztups.vercel.app 이다. Vercel 배포 `dpl_FG5YbB7RtME9e36byhezFiPAAE4Z`를 연결했다. 각각 해당 커밋의 깨끗한 Git 스냅샷을 사용했다. Windows 이후의 웹 메뉴 수정은 웹에만 적용한다. 이전 배포와 자산은 유지했다.

## 반영한 기능

- SEC 직접 요청의 403은 남아 있다. 원인 정책을 특정하지 않았으며, Apple 공식 IR PDF와 Microsoft 공식 투자자 페이지의 DOCX 원문을 대체 수집 경로로 추가했다. 발행사·기업 식별자·양식·기간과 본문 해시를 확인한다. Microsoft 발표일을 얻지 못한 자료는 최초 공개 확인일로 표시한다.
- 2026-11-05 확보한 자료에서 삼성전자·SK하이닉스·현대차·NAVER·Apple·Microsoft의 최소 근거 조건을 충족했다. 기존 자료의 준비 상태이며 새 6기업 AI 토론이나 투자 정확도 검증 결과가 아니다.
- 웹 기업 관계 지도에 공식 출처 6개 연결을 제공한다. Apple 공급망 FY2023 기록 등 과거 자료를 표시하고 확인 사실·긍정/위험 가설·추가 확인 데이터를 분리한다. NVIDIA는 참조 기업이다. 지도는 수동 관리하며 실시간 공급량이나 주가 상관관계를 계산하지 않는다. 토론 생성 경로와 별도로 유지한다.
- 관리자 공통 평가 기준에서 Ragas 사례별 점수 JSON 반입, 원문 제외, 누락 수 보존과 지표별 집계 재계산을 제공한다. 버전·판정 모델·데이터셋·설정 해시를 기록한다. 반입은 사용자가 제공한 결과이며 독립적인 외부 인증이 아니다.
- Google PageSpeed Insights, Langfuse, FinQA의 공식 경로를 안내한다. Langfuse API 자동 연결은 하지 않았다. Streamlit은 같은 숫자 기록을 로컬에서 읽는 소스용 화면이며 EXE에 포함하지 않는다.

## 수행 범위

Python 문법 검사, Vite 프로덕션 빌드, ZIP CRC/필수 자원/비밀 파일 이름 검사와 공개 다운로드·HTML/번들 반영을 확인했다. 웹 공개 경로는 HTTP 200이며 관리자 데이터는 기존 로그인·운영자 권한을 사용한다. HTTP 200은 관리자 권한 검증을 대신하지 않는다. DB 스키마·권한 변경은 없었다.

- ZIP: 462,912,723 bytes / 9,816 entries
- SHA-256: `82c58269f04fd25d873fdb62f7a5d575b409a3b4773bce0c56f1b347dac31d78`
- 공개 GitHub 자산 digest·체크섬 일치 및 ZIP HEAD 200 확인. 463MB 파일 전체를 재다운로드하지 않았다.
- 배포 EXE 실행·새 테스트 실행·전체 회귀·AI 분석·Ragas 판정·성능/품질 벤치마크는 사용자 요청으로 보류했다. 테스트 파일은 작성만 했다. 이전 버전의 테스트 통과 수를 이번 버전 결과로 사용하지 않는다.
- 패키징 중 선택적 의존성 관련 경고가 남았다. 실제 분석 경로에 대한 영향은 실행 검증 전까지 확인하지 않았다.

관련 이슈: #29, #30, #31. [평가 사용법](standard-evaluation.md).
