# MarketCouncil 개선 로드맵

열려 있는 GitHub 이슈, 개발 보고서(`docs/project-summary-2026-10-11.md`), 검증 기록에 남은 한계를 모아 정리한 개선 목록입니다. 작업을 시작하거나 끝낼 때 상태를 갱신합니다. 우선순위는 제안이며 사용자가 정합니다.

상태 표기: `진행 중` · `대기` · `외부 설정 필요` · `완료`
기준일: 2026-11-10 (브랜치 `debate_focus`, 최종 갱신 커밋 이후 기록)

## P0. 진행 중인 배포·기능 마무리

| 항목 | 이슈 | 상태 | 남은 일 |
| --- | --- | --- | --- |
| Windows 0.9.0 패키지와 웹 다운로드 안내 갱신 | #35 | 진행 중 | 깨끗한 스냅샷 빌드, ZIP·SHA-256, EXE self-check, GitHub 사전 릴리스, 웹 한·영 안내 수정과 Vercel 배포, 태그 |
| 로그인 시 일일 분석 확인 창·실행 이력 | #34 | 진행 중 | 구현은 커밋됨. 실제 창 확인과 0.9.0 배포 후 이슈 종료 |
| 발행사 원문 대체 수집·관계·공통 평가 화면 배포 기록 | #31 | 진행 중 | 실제 배포 커밋·URL·검증 결과를 이슈에 마무리 기록 |
| 0.5.0 배포 이슈 정리 | #23 | 대기 | 이후 배포로 대체된 항목을 확인하고 종료 조건 정리 |

## P1. 근거·결과 품질 결함 (#21 남은 항목)

| 항목 | 관련 코드 | 상태 |
| --- | --- | --- |
| 중첩 결과 형식 서버/입력/읽기 검증과 상세 화면 오류 격리 | `frontend/src/resultUpload.js`, `supabase/discussions.sql`, `frontend/src/main.jsx` | 대기 (일부 커밋됨, 잔여 확인 필요) |
| 검색 의도(`search_focus`)와 검증된 출처 유형(`source_type`) 분리 — 언론 기사가 공식 자료로 표시되는 문제 | `tools/source_collector.py`, `app/debate_workflow.py`, `tools/evidence_catalog.py` | 완료 (2026-11-10, 미분류는 `unknown`, 집계 사이트 `official`→`news`, #21 기록. 실제 분석 결과·기존 저장 결과는 미검증) |
| 공식·커뮤니티 결과 저장 버튼 숨김과 UUID/북마크 키 제약 불일치 | `frontend/src/data.js`, `Discussions.jsx`, `supabase/user-lists.sql` | 대기 |
| 공식 결과 비공개 전환 시 날짜 선택 행이 남는 문제 | `Discussions.jsx`, `desktop/daily_official.py`, `desktop/cloud.py` | 대기 |
| 공식 지정·업로드·공개 범위 변경 후 목록 미갱신 | `frontend/src/main.jsx` | 일부 수정됨 (재확인 필요) |

## P2. 평가 체계 — "환각이 줄었는가"를 측정 가능하게

현재 평가 도구는 구현됐지만 **사람 정답 기반 실제 점수는 아직 없습니다.**

1. 기업·문서·기준일로 분리한 고정 평가 데이터셋 구축(사람 검수 질문·정답 근거 ID). 절차·후보 목록 도구 준비 완료([evaluation-dataset.md](evaluation-dataset.md), `tools/rag_dataset_candidates.py`). **사람 정답 작성 대기**.
2. 검색 Recall@k·Precision@k·MRR·지연 측정(`tools/rag_benchmark.py`).
3. 단일 LLM 답변 / RAG 답변 / 토론을 같은 조건에서 비교.
4. 주장–인용 의미 지지 평가: 사람 정답 큐(`tools/quality_benchmark.py`)와 Ragas 결과 반입(`tools/external_evaluation.py`). `semantic_status`를 `not_evaluated`에서 실제 판정으로 확장.
5. 관련 이슈: #24(단계별 시간·토큰·비용과 답변 근거 품질) 종료 조건 정리.

## P2-1. 코드 구조

- ~~미사용 `app/workflow.py` 삭제, 토론 상세 화면을 `DebateDetail.jsx`로 분리~~ 완료(2026-11-10).
- 남은 후보: `bull_main`·`bear_main`·`video_debate_main` 등 단독 CLI 정리 여부 결정, `config` import 시 키 검사 지연, 역할별 모델 설정, `desktop/main.py` UI·로직 분리.

## P3. 검색·인용 품질

- 문단·표를 보존하는 청킹(`rag/text_splitter.py`), 키워드+벡터 하이브리드 검색, 재순위(reranker) 후보 검토.
- 날짜 누락·중복 출처 정리, 기준일 필터를 후보 절단 전에 적용하는지 회귀 테스트 유지(`rag/retriever.py`).
- 모든 변경은 P2의 고정 데이터셋으로 전·후 비교 후 채택.

## P4. 토론 편향과 안전성

- 발언 순서(Bull 선발) 효과 측정: 순서 교체·독립 최초 분석 비교.
- 외부 문서 내 프롬프트 인젝션 방어 강화(수집 본문을 지시로 해석하지 않도록 프롬프트·전처리 점검).
- 다른 모델 조합의 비용·지연·품질 비교(`config/__init__.py`의 `MODEL_NAME`).

## P5. 사용자·운영 흐름

| 항목 | 이슈 | 상태 |
| --- | --- | --- |
| 일반 사용자 SMTP 로그인 발송과 새 PC 전체 분석 검증 | #8 | 외부 설정 필요 |
| GitHub OAuth 로그인 활성화와 실제 업로드 검증 | #10 | 외부 설정 필요 |
| 자동 분석 입력·재시도·단계 복구 — 일반 수동/CLI 분석에도 복구 연결 검토 | #17 | 대기 |
| 기업별 공시·IR 원문 준비 — 미국 기업 SEC 제한, 다음 분기 IR 링크 자동 발견 | #29 | 대기 |
| 출처 기반 기업 관계도 — 현재 로컬 개발 전용, 공개 여부 결정 | #30 | 대기 |
| 웹 성능(Lighthouse 모바일 63점, 단일 측정) 개선 | — | 대기 |

## P6. 저장소·개발 환경 정비

- `master`가 `debate_focus`보다 약 149커밋 뒤처짐 → 기본 브랜치 전략 결정 후 AGENTS.md 브랜치 규칙 갱신.
- AGENTS.md의 단계별 구축 순서(이미 완료)를 현재 단계(평가·품질·운영)로 갱신.
- ~~테스트 실행 통일과 CI~~ 완료(2026-11-10): `python -m tests`(456개 수집), `.github/workflows/ci.yml`. 첫 CI에서 Tk 정리 충돌·#29 이후 미갱신 테스트 11건·CI venv 부재 테스트 1건을 발견해 테스트만 수정, CI 통과(#36, 웹·Python 모두 성공, Python skipped=12). CI는 설치 스크립트의 소스 실행 경로를 검사하지 않음(로컬 venv에서만).
- 건너뛰는 테스트 11개(로컬)의 사유 검토 — 대기.
- ~~운영 Supabase 테이블·RLS·RPC와 `supabase/*.sql` 일치 비교, Vercel 프로덕션 배포 커밋 확인~~ 완료(2026-11-10, 읽기 전용 조회만):
  - Supabase `snembdnkylggbxtxfqyz`: 테이블 6개·RLS·CHECK/FK 제약, 정책 9개, 함수 6개(본문 해시 일치, 줄바꿈만 CRLF)·실행 권한, 트리거 2개가 SQL과 일치. 마이그레이션 이력은 비어 있음(SQL 편집기로 직접 적용).
  - 남은 차이(#37, 저장소 SQL 수정 완료·운영 DB 적용 대기 — `supabase/table-privileges.sql`, `supabase/storage.sql`): Supabase 기본 권한 때문에 `discussions`에 anon의 INSERT/UPDATE/DELETE/TRUNCATE 등, 여러 테이블에 TRUNCATE·REFERENCES·TRIGGER가 남아 있음(쓰기는 RLS가 막지만 TRUNCATE는 RLS 대상 아님). `analysis-results` 버킷(공개, 스토리지 정책 없음)은 SQL 파일에 정의가 없음. 보안 권고: 유출 비밀번호 보호 꺼짐.
  - Vercel: 운영 주소는 `dpl_HcrVD9T18e1HJS9cEpyr9K25UgYN`(`465ee2e`, web-v0.15.2). `dpl_Ft87dzcHnCH84X92P6zHA9kVtapz`는 #35의 0.9.0 후보로 별칭 미연결(Git 커밋 메타 없음, 빌드 커밋 미검증). `60097cd` 대비 frontend 변경 커밋 5개 미배포. `docs/deployment-versions.md`에 web-v0.15.2 항목 누락.
- ~~의존성 버전 고정~~ 완료: `requirements/lock-windows.txt`(검증된 venv 스냅샷), `requirements/test.txt`.
- Linux 공개 서버 배포(`docs/deployment.md`)는 구성만 준비됨 — 진행 여부 결정.

## 갱신 방법

- 항목을 시작하면 `진행 중`, 끝나면 `완료`와 검증 범위·관련 커밋/이슈를 적습니다.
- 새 문제는 먼저 GitHub 이슈를 만들거나 기존 이슈를 재사용한 뒤 여기에 연결합니다.
- 완료 항목이 쌓이면 별도 절로 옮기거나 삭제해 문서를 짧게 유지합니다.
