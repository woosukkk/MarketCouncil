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

