# Desktop distribution

Windows 64-bit MarketCouncil.exe runs analysis locally and ships no owner credentials, saved results, document archive or Chroma database. API keys and Supabase sessions stay in process memory and must be entered again after restart. Python bytecode is packaged inside the executable; packaging is not a guarantee against reverse engineering.

Install Docker Desktop first and start it. The app prepares its bundled SearXNG configuration in %LOCALAPPDATA%/MarketCouncil/infra. On first use, an empty local Chroma collection returns no report excerpts; the analysis uses available web and financial evidence. Only a populated report library loads BGE-M3 and downloads its model to the user data folder. Documents must have matching company metadata to appear in company-specific searches.

Enter company name and a Yahoo Finance ticker explicitly (e.g. 000660.KS or AAPL). Availability depends on upstream financial data, public documents and search sources. DART API key is optional and improves Korean filing collection. The user's OpenAI key pays for analysis calls.

Login uses the existing email-link flow. Copy the login button URL from the email without opening it, then paste it into the desktop account connection field. Tokens are one-use; request a new email if already consumed. Default Supabase mail delivery only supports project team emails until custom SMTP is configured.

Analysis saves locally first. Upload is explicit and uses the authenticated user's token. The discussions table defaults to private; uploaded payloads contain result fields and cited excerpts only. Same account + same local result file reuses an ID. My page lists own discussions, and the owner can publish to the community or create a random share link. Returning to private revokes subsequent shared/public reads, not copies already downloaded. Existing public example results remain public.

Apply supabase/discussions.sql once. Anonymous listing can read public discussions only. Shared discussions use a token-gated RPC; private rows cannot be read through it.

Build with PyInstaller from MarketCouncil.spec or the documented command in build_desktop.ps1. No fresh paid analysis is executed during build or tests. Clean-machine execution and real mailbox sign-in should be tested before wider distribution.

## Daily official discussion

The configured official editor selects one own uploaded result for the current Asia/Seoul date. The database permits one selection per date; changing the selection replaces the daily pointer. This publishes that result and revokes its old share link. Other users cannot assign official status. No scheduled or paid analysis is triggered.

Replacing today's selection leaves the previous discussion public. Its owner can separately return it to private. Historical daily selections remain in the archive; private discussion contents remain inaccessible.

Legacy local automatic public archive upload is disabled in .env.result-upload. Use desktop account upload for new private results. Existing public examples remain available.

## Changed files

| Files | Change |
| --- | --- |
| desktop/main.py, desktop/cloud.py, desktop/__init__.py | Local Windows UI, in-memory login/API keys, private user-token upload |
| build_desktop.ps1, .gitignore | Standalone build, runtime data collection, exclude build outputs |
| tools/financial_data.py | Explicit validated company ticker |
| rag/retriever.py, tools/bull_tools.py, tools/bear_tools.py | Company-scoped search and lazy model loading for empty libraries |
| frontend/src/main.jsx, frontend/src/Account.jsx, frontend/src/Discussions.jsx | My discussions, community, sharing, official selection, program download |
| frontend/src/landing.css, frontend/vercel.json | New screen layout and download route |
| supabase/discussions.sql | Private/shared/public access and editor-only daily official selection |
| test_desktop.py | Upload boundary, login URL validation, ticker selection and retrieval isolation |
| docs/desktop-distribution.md, docs/result-publishing.md | Distribution flow and disable legacy public auto-upload |

Unrelated existing working-tree changes were preserved.

## Validation

- Eight Python desktop/result-publishing tests passed.
- Four frontend data tests passed.
- Source initialization checks passed, including an empty local Chroma collection and the GUI.
- Live disposable-account checks passed for private isolation, token sharing, revocation, public reads, editor-only official selection and one selection per date. Both disposable users and their results were cleaned up.
- Legacy RESULTS_AUTO_UPLOAD is false in the local configuration; no credentials were changed or included in distribution.
- The package file list contains the browser driver and Crawl4AI JavaScript resources, and excludes owner environment files, results, documents and Chroma data.

- Frozen executable check passed: GUI, workflow initialization, empty Chroma storage, bundled browser driver and Crawl4AI JavaScript resources. No paid analysis was executed.
- Archive check passed: executable entry matches current source and required dynamic modules are present; no embedded project secret-key constants were found.
- Preview executable size: 450,849,584 bytes. A SHA-256 file accompanies the download.
- Actual mailbox completion, a fresh paid analysis and execution on a separate clean PC remain unverified.

The unsigned single-file program extracts its bundled runtime at launch, so startup can take some time. Source packaging does not conceal the existing public GitHub repository or provide absolute source-code protection.

## Published preview

Download: https://frontend-six-pi-h5i7tztups.vercel.app/download
Release: https://github.com/woosukkk/MarketCouncil/releases/tag/desktop-v0.1.0

GitHub's uploaded asset digest matches the local executable SHA-256. Production deployment completed and anonymous HTTP checks passed for /, /app, /download and the public executable download. The production community page completed its public-only lookup; anonymous My Page access shows the login prompt.

## 기업명 자동 종목 조회

기업명 입력 후 기업 찾기 또는 분석 실행을 누르면 종목을 조회합니다.
국내 한글 이름은 한국거래소 KIND의 KOSPI/KOSDAQ 상장 목록에서 조회하며,
해외 기업은 영문 이름으로 Yahoo Finance의 주식 검색을 사용합니다.
후보가 하나면 자동 선택하고, 여러 개면 기업명·거래소·종목코드를 보고 선택합니다.
조회 후 분석 실행을 눌러 실제 분석을 시작합니다. 이름을 변경하면 다시 조회합니다.
조회 실패나 후보 미선택 상태에서는 유료 분석을 시작하지 않습니다.
국내 상장 목록은 실행 중에만 캐시합니다. 비상장 기업과 KONEX는 지원하지 않습니다.
한글 해외 기업명 번역이나 검색 결과의 확정적인 동일 기업 판별은 제공하지 않습니다.

## Desktop 0.2.0 준비 상태와 진행 안내

준비 상태 탭에서 API 키 입력 여부, 검색 서버 응답, Docker 실행 여부, 브라우저 설치 기록을 확인합니다. 키 유효성과 실제 검색 기능은 분석 실행 시 확인하며 준비 확인으로 OpenAI 호출은 하지 않습니다.
분석 중 실제 로그에 맞춰 자료 수집, 관점 분석, 토론 라운드, 최종 정리 단계를 표시합니다. 진행률을 추정하지 않습니다. 결과 폴더 버튼과 GitHub 사용자의 웹 JSON 가져오기 안내를 추가했습니다.
준비 상태와 단계 판별 테스트, 기존 기업 조회·데스크톱 테스트 총 12개 통과. 새 PC와 유료 분석은 검증하지 않았습니다.


## Desktop 0.3.0 삼성전자 공식 게시

공식 운영자 이메일 계정을 연결한 후 본인 API 키를 입력하고 삼성전자 분석 후 오늘 공식 게시 버튼을 누릅니다. 기업 검색 없이 삼성전자 005930.KS로 실행합니다. 운영자 권한과 한국 시간 기준 오늘 공식 지정 여부를 유료 분석 전에 확인하며, 오늘 지정이 있으면 중단합니다. 분석 후 JSON을 로컬에 먼저 저장하고 비공개 업로드와 기존 공식 지정 RPC를 순서대로 실행합니다. 공개되는 내용은 결과와 인용 근거이며 원문 전체는 업로드하지 않습니다.
실패 시 로컬 결과를 웹 마이페이지에서 가져와 공식 지정할 수 있습니다. 여러 운영자나 다른 웹 화면에서 동시에 지정하면 기존 RPC 동작대로 오늘 지정이 교체될 수 있습니다. 자동 예약 실행은 추가하지 않았습니다.
공식 권한·중복·삼성전자 검증·토큰 갱신 테스트를 포함해 Python 테스트 16개 통과. 실제 유료 분석 및 실제 공식 게시 호출은 실행하지 않았습니다.


## Desktop 0.4.0 입력 설정과 배포

기업명·검색 주소 기억하기 버튼으로 비밀 정보가 아닌 두 입력을 로컬 preferences.json에 저장합니다. API 키·이메일·로그인 토큰은 저장하지 않습니다. 준비 상태 탭의 새 버전 확인 버튼은 GitHub의 desktop 버전만 비교합니다. 웹 버전과 비공개 초안은 제외하며 네트워크 실패를 안내합니다.

폴더형 배포는 ZIP을 한 번 풀고 MarketCouncil 폴더의 MarketCouncil.exe를 실행합니다. _internal 폴더를 함께 유지해야 합니다. 매 실행 시 전체 런타임 압축 해제 과정을 제거합니다. 다운로드 크기와 실제 시작 속도 개선 폭은 빌드 후 측정해야 하며, 분석 모델은 필요할 때 별도로 내려받습니다. 일체형 0.3.0도 이전 릴리스에서 유지합니다.

관련 Python 테스트 14개와 웹 테스트 8개 통과. 실제 삼성전자 분석은 별도 실행 검증 중이며, 다른 사용자 PC에서는 검증하지 않았습니다.

## 2026-10-10 실제 사용자 검증

새 Gmail SMTP 발송과 이메일 링크 로그인 완료. 요청에 따라 공식 운영자 권한을 새 계정으로 교체했습니다. 삼성전자 실제 분석 1회를 실행해 2라운드 결과를 로컬 저장한 뒤, 웹에서 비공개 가져오기와 오늘 공식 공개 지정을 완료했습니다. 로그인 토큰 없는 공개 열람도 확인했습니다. 게시된 결과는 약 77KB이며 원문 문맥과 인증 필드를 포함하지 않습니다.

실제 관심기업 추가·관련 공개 분석·공식 토론 상세 표시 확인. PC 버튼에서 분석과 게시를 한 번에 완료하는 흐름 전체와 다른 사용자 PC 실행, 실제 토론 삭제는 아직 검증하지 않았습니다.
