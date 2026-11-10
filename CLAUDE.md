# CLAUDE.md

MarketCouncil 저장소에서 작업하는 Claude를 위한 안내서입니다. 이 프로젝트는 계속 개선해 나가는 중이므로 이 문서도 함께 갱신합니다.

@AGENTS.md

> 위 `AGENTS.md`가 **작업 규칙의 원본**입니다(승인 규칙, Git·이슈·PR 규칙, 분석 출력 원칙, 토큰 사용 규칙). 이 문서는 그 규칙을 반복하지 않고, 저장소 구조·실행 방법·불변 원칙·개선 방향을 보충합니다. 두 문서가 충돌하면 `AGENTS.md`를 따르고, 충돌 사실을 사용자에게 알립니다.

## 1. 프로젝트 요약

- **무엇**: 같은 근거 카탈로그를 두고 Bull(상승)·Bear(하락) 에이전트가 토론하고 Moderator가 쟁점·합의점·추가 확인 데이터를 정리하는 근거 기반 투자 리서치 시스템.
- **구성**: 분석 엔진은 사용자 Windows PC에서 실행(Python · LangGraph · OpenAI `gpt-5-mini` · BGE-M3 + ChromaDB · SearXNG(Docker)). 웹(React 19 + Vite, Vercel)은 저장된 결과의 열람·보관·공유만 담당. Supabase가 인증·저장·RLS를 담당.
- **대상 기업(6)**: 삼성전자, SK하이닉스, 현대자동차, NAVER, Apple, Microsoft (`tools/company_profiles.py`).
- **운영 주소**: https://frontend-six-pi-h5i7tztups.vercel.app (`/`, `/app`, `/app?view=my`, `/app?view=admin`, `/download`)
- **GitHub**: https://github.com/woosukkk/MarketCouncil

### 브랜치와 버전 상태 (2026-11-10 기준)

- **서비스 개발 브랜치는 `debate_focus`** 입니다. README도 이 브랜치를 구현 기준으로 안내합니다. `master`는 2026-08 초 이후 갱신되지 않아 `debate_focus`보다 약 149커밋 뒤처져 있습니다.
- `archive/B-B-N`, `archive/emotional-axis`는 과거 실험 브랜치, `origin/feature/web-deployment`는 원격에만 있습니다.
- 태그: 웹 `web-vX.Y.Z`(최신 `web-v0.15.2`), Windows `desktop-vX.Y.Z`(최신 공개 `desktop-v0.8.1`, `0.9.0`은 #35에서 배포 준비 중).
- 작업 시작 전 `git status`로 **사용자의 미커밋 변경**을 확인하고 절대 덮어쓰거나 함께 커밋하지 않습니다.

## 2. 디렉터리 지도

| 경로 | 역할 |
| --- | --- |
| `agents/` | 에이전트 로직(`*_agent.py`)과 프롬프트(`*_prompt.py`). 프롬프트는 반드시 별도 파일에 둡니다. 핵심: `analysis_debate_agent.py`(LangGraph 토론 그래프), `moderator_agent.py`, `bull_agent.py`, `bear_agent.py` |
| `app/` | 워크플로와 진입점. `debate_workflow.py`(전체 파이프라인), `recoverable_debate_workflow.py`(단계 체크포인트 복구), `comparison_workflow.py`(공통 근거 수집), `regime_workflow.py`(시장 국면), `evidence_preflight.py`, `prepare_company_evidence.py`(근거 준비 CLI), `debate_main.py`(CLI 진입점), `streamlit_app.py`(로컬 뷰어) |
| `tools/` | 수집기·검증기·저장소. DART/SEC/발행사 IR 수집, `evidence_catalog.py`, `evidence_readiness.py`, `citation_quality.py`, `financial_data.py`, `structured_response.py`(OpenAI 구조화 응답·재시도), `run_metrics.py`(단계 시간·토큰·비용), `result_validation.py` |
| `rag/` | 문서 로딩·청킹·색인·검색. `retriever.py`는 기업·기준일 필터를 적용 |
| `desktop/` | Windows 앱(`main.py` Tkinter UI, `cloud.py` Supabase 업로드, `daily_official.py`·`daily_prompt.py`·`daily_history.py` 일일 공식 게시와 실행 이력 창) |
| `frontend/` | React 웹. `src/main.jsx`(라우팅), `Admin.jsx`, `Account.jsx`, `Discussions.jsx`, `messages.en.js`(영문 UI 사전), `tests/*.test.js` |
| `supabase/` | 스키마·RLS·RPC SQL. 운영 DB에 직접 적용하는 파일이므로 변경은 반드시 별도 승인 |
| `tests/` | Python `unittest` 테스트(약 58개 모듈) |
| `docs/` | 기능 설계·검증·배포 기록. 날짜가 붙은 문서는 해당 시점의 검증 기록 |
| `config/` | `config/__init__.py`가 `.env`를 읽음(**`OPENAI_API_KEY`가 없으면 import 시 예외**). 예시는 `config/.env.example` |
| `scripts/`, `MarketCouncil.spec` | 실행 배치 파일과 PyInstaller 빌드 |
| `infra/`, `compose.yaml`, `Dockerfile*` | SearXNG·Caddy·Linux 배포 구성(서버 공개 배포는 미완료) |
| `benchmarks/` | 평가 데이터셋 템플릿과 토큰 단가 스냅샷 |

읽지 않는 경로: `.env*`, `venv/`, `__pycache__/`, `results/`, `documents/`, `vector_db*/`, `build/`, `dist/`, `frontend/node_modules/` (AGENTS.md 토큰 규칙과 동일).

## 3. 분석 파이프라인

```
기업명/티커 확인 → 근거 준비 gate(공시·IR 원문, 유료 호출 전)
→ 공통 근거 수집(재무·RAG·웹·DART/SEC·3년 역사 자료) → EvidenceCatalog
→ 시장 국면 분석 → Bull/Bear 최초 분석 · 심리 · 영상 · 탐색
→ 토론 그래프: create_agenda → bull_turn → bear_turn → moderator_review
   → (새 정보가 있으면 next_round, 아니면 summary)
→ 인용 검증(identity/numeric) → 로컬 JSON 저장 → (선택) 비공개 업로드 → 공유/커뮤니티/공식 지정
```

- 토론 의제는 최대 3개, 라운드는 2~3회이며 새 유효 근거나 실질적 변화가 없으면 종료합니다.
- 카탈로그에 없는 인용은 유효 근거에서 제외하고, 유효 인용은 저장된 원문으로 복원합니다. `semantic_status`는 아직 항상 `not_evaluated`입니다.

## 4. 개발 명령어 (Windows, 프로젝트 루트)

```powershell
# Python 테스트 전체 (unittest 클래스 + 모듈 수준 test_ 함수까지 수집)
venv\Scripts\python.exe -B -m tests
venv\Scripts\python.exe -B -m tests -p test_evidence_catalog.py -v   # 단일 파일
# 테스트 의존성만 설치: pip install -r requirements/test.txt -c requirements/lock-windows.txt

# 웹
cd frontend; npm ci; npm test; npm run build; npm run dev

# CLI 분석 (유료! 사용자 지시 없이 실행 금지)
venv\Scripts\python.exe -m app.debate_main

# 근거 준비 점검 (공개 원문 수집만, AI 호출·업로드 없음)
venv\Scripts\python.exe -m app.prepare_company_evidence --refresh --output evidence-readiness.json

# 로컬 Streamlit 뷰어
scripts\view_debate.bat
```

테스트 주의사항:
- `python -m unittest discover`는 모듈 수준 `test_` 함수(8개 파일, 30개)를 수집하지 않습니다. 항상 `python -m tests`를 사용합니다(`tests/__main__.py`, `tmp_path` 인자 지원).
- CI(`.github/workflows/ci.yml`): Python 테스트는 Windows·Python 3.11, 웹은 Ubuntu·Node 22에서 `npm test`·`npm run build`를 실행합니다.
- 의존성 버전은 `requirements/lock-windows.txt`(검증된 venv 스냅샷)가 기준입니다. 업그레이드 시 함께 갱신합니다.
- 테스트는 모의 API 응답과 더미 키를 사용합니다. 실제 키가 필요한 테스트를 새로 만들지 않습니다.
- 전역 `sys.modules` 모의로 다른 테스트를 오염시키지 않습니다(#21에서 실제 문제였음).
- UI 문구를 바꾸면 `frontend/src/messages.en.js`의 영문 항목도 함께 갱신합니다.

## 5. 불변 원칙 (깨면 안 되는 것)

**비용과 운영 안전**
- 유료 OpenAI 분석, 공식 게시, 운영 Supabase 변경, 릴리스 게시는 사용자가 명시적으로 지시할 때만 실행합니다. 검증은 모의·오프라인·기존 결과로 먼저 합니다.
- 인증·권한·`insufficient_quota` 오류는 재시도하지 않고 즉시 중단합니다(`tools/structured_response.py`).
- 하루 공식 분석 시도는 복구 포함 최대 2회입니다. 이미 게시된 날은 추가 분석하지 않습니다.

**근거 무결성**
- 기업·기준일 범위를 벗어난 자료(다른 기업, 기준일 이후 자료)를 근거로 쓰지 않습니다. 검색은 후보를 자르기 **전에** 기준일 필터를 적용해야 합니다.
- 날짜는 한국 시간(Asia/Seoul) 기준으로 정규화합니다. 시간대 없는 시각·불명확한 날짜는 "날짜 미상"으로 둡니다.
- 제목 목록·검색 snippet·오류 페이지·메타데이터를 원문 근거로 인정하지 않습니다. 최신 필수 자료를 못 구하면 과거 캐시로 대체하지 않습니다.
- 검색 의도(`search_focus`)와 검증된 출처 유형(`source_type`)을 섞지 않습니다.
- 확인되지 않은 값은 추정하지 말고 `확인 불가` / `추가 데이터 필요`로 남깁니다(통화, 공개일 등 포함).
- 체크포인트는 기업·티커·날짜·모델·코드/프롬프트 서명·원문 해시로 범위를 고정합니다. 이 서명에 영향을 주는 코드를 바꾸면 재사용 무효화가 제대로 되는지 확인합니다.

**데이터 공개 경계**
- 클라우드에는 결과 JSON과 인용 발췌만 올립니다. PDF·기사 본문·검색 문맥·임베딩·Chroma·로컬 경로는 로컬에만 둡니다.
- 비밀값(OpenAI·DART 키, Supabase secret, OAuth secret, 로그인 링크)은 코드·`VITE_*` 변수·이슈·커밋·로그·문서에 넣지 않습니다. 진단 기록에는 단계·오류 종류·HTTP 상태만 남깁니다.
- 개인 토론은 기본 비공개입니다. 공개 범위를 바꾸는 코드는 기존 공개 범위를 덮어쓰지 않아야 합니다.

**정직한 기록**
- 실행하지 않은 검증을 통과로 쓰지 않습니다. "확인함 / 모의로 확인 / 미검증"을 구분해 기록합니다.
- 인용이 있다는 것이 주장의 사실성을 보증하지 않습니다. 품질 수치를 정확도·환각률로 과장하지 않습니다.

## 6. 개선 작업의 흐름

1. **이슈 확인**: 관련 GitHub 이슈와 `docs/ROADMAP.md`를 먼저 확인합니다. 같은 문제의 이슈가 있으면 재사용합니다.
2. **조사와 제안**: 관련 파일만 읽고 현재 동작 → 문제 → 변경안 → 수정 파일 목록을 제시하고 승인을 받습니다(AGENTS.md 승인 규칙).
3. **최소 변경 구현**: 기존 규칙과 구조를 재사용하고 불필요한 리팩터링·의존성 추가를 피합니다. 새 함수에는 타입 힌트를 붙입니다.
4. **검증**: 관련 Python 테스트, 웹 변경 시 `npm test` + `npm run build`. 결과 개수와 범위를 정확히 보고합니다.
5. **커밋**: 영어 `type: subject (#이슈)` 형식, 기능 단위로 나눠 커밋합니다. 사용자의 미커밋 변경은 포함하지 않습니다.
6. **기록**: 의미 있는 기능·수정은 `docs/`에 설계·검증·한계를 남기고, 로드맵 상태를 갱신합니다. 배포는 `docs/deployment-versions.md`와 이슈에 기록합니다.

### 배포 시 (요약, 상세는 AGENTS.md · docs/deployment-versions.md)
- 승인된 변경만 커밋한 뒤 **깨끗한 커밋 스냅샷(git archive)** 에서 빌드합니다. 미커밋 작업이 섞이면 안 됩니다.
- 기능 추가는 minor, 수정은 patch. 실제 배포 커밋에 annotated tag를 붙이고, 이전 릴리스 자산은 덮어쓰지 않습니다.
- 웹: Vercel 프로덕션 배포 후 `/`, `/app`, `/download`와 실제 JS 번들 반영을 확인합니다.
- Windows: ZIP·SHA-256·민감 파일 제외·EXE self-check를 확인합니다.

## 7. AGENTS.md와 실제 상태의 차이 (사용자 결정 필요)

다음은 AGENTS.md의 내용이 현재 저장소 상태와 다른 부분입니다. 임의로 고치지 말고, 관련 작업 시 사용자에게 확인합니다.

- **브랜치 규칙**: AGENTS.md는 `main`/`develop`/`feature/*`/`hotfix/*`를 정의하지만 실제로는 `master`(정체)와 `debate_focus`(서비스)를 사용합니다.
- **단계별 구축 순서**: "단일 LLM → … → 멀티 에이전트" 순서는 이미 모두 구현된 상태입니다. 현재 단계는 품질 평가·근거 품질·운영 안정화입니다.
- **개발 기록**: Notion 기록 규칙이 있으나 이 세션 환경에서 Notion 연결 여부는 별도로 확인해야 합니다.

## 8. 자주 걸리는 함정

- `config`를 import하면 `OPENAI_API_KEY`가 없을 때 예외가 납니다. 테스트에서는 환경 변수를 더미로 주입합니다.
- Windows 경로·인코딩: 배치 파일은 `chcp 65001`, `PYTHONUTF8=1`을 사용합니다. 한글 파일명·예약 작업 문자열의 유니코드 보존을 확인합니다.
- `frontend`의 Supabase 값은 공개 키(`VITE_SUPABASE_PUBLISHABLE_KEY`)만 사용합니다.
- 작업 트리 파일은 Windows에서 CRLF, 저장소는 LF입니다. Linux 셸에서 git을 쓸 때는 `git -c core.autocrlf=true ...`로 실행해야 전체 파일이 수정된 것처럼 보이지 않습니다.
- 기업 프로필은 Python(`tools/company_profiles.py`)과 웹(`frontend/src/companyProfiles.json`)에 각각 있습니다. 기업을 추가·수정할 때 둘을 함께 맞춥니다.
- SEC 직접 접근은 제한될 수 있으며, 이때는 발행사 공식 공시 사본 경로를 사용합니다(제3자 미러 금지).
- 일반 수동 PC/CLI 분석에는 단계 복구가 연결되어 있지 않습니다(자동 공식 분석 경로만 해당).
