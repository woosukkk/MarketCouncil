# User service

Supabase Auth uses email login links and creates an account on first sign-in. Configure Site URL to the production /app URL. Vercel uses VITE_SUPABASE_URL and VITE_SUPABASE_PUBLISHABLE_KEY; never use a server secret in frontend configuration.

Apply supabase/user-lists.sql once. watchlist and saved_analyses use user_id ownership and row level security for all operations, with anonymous access revoked. Saved analysis IDs omit content versions so bookmarks follow the current published result. Account deletion cascades the personal lists.

Public research stays public. Personal lists contain references and company metadata, not copied analyses or PDFs. Watchlist entries are manual; adding one does not execute a new analysis.

Supabase default mail delivery is for project team addresses only. A custom SMTP provider is required before opening email sign-in to general users. Email delivery and login-link completion require a real mailbox test.

## 사용자 이용 흐름 개선

웹 로그인 화면에 GitHub 로그인을 준비했습니다. Supabase의 공개 인증 설정에서 GitHub 활성화가 확인된 경우에만 버튼을 활성화합니다. GitHub OAuth 앱의 Client ID/secret은 Supabase 인증 설정에만 보관하며 프런트엔드나 저장소에 넣지 않습니다.

마이페이지에서 분석 JSON 파일을 직접 가져올 수 있습니다. PC 프로그램은 로그인 없이 로컬 분석을 실행하고, 사용자는 웹에서 로그인한 뒤 파일을 선택하여 비공개로 보관합니다. 이메일 기반 PC 계정 연결은 기존 운영자용 흐름으로 유지됩니다. 새 프로그램 빌드 없이 GitHub 사용자 결과 보관이 가능합니다.

원본 파일 10MB, 압축 결과 1.9MB 한도를 확인하며 선택된 결과 필드와 인용 근거만 전송합니다. 전체 검색 문맥과 원문은 제외합니다. 동일 사용자·동일 압축 결과는 동일 ID를 사용하고 기존 결과의 공개 범위를 덮어쓰지 않습니다. 다른 업로드 경로에서 이미 저장한 동일 결과는 별도 ID가 될 수 있습니다.

가입·프로그램 설치·결과 가져오기를 마이페이지에 안내하고 다운로드 안내를 0.1.1 및 기업명 조회 방식으로 갱신했습니다.

검증: 프런트엔드 테스트 7개와 빌드 통과. 새 GitHub 제공자 설정·실제 로그인 완료와 실제 사용자 업로드는 외부 계정 설정 완료 후 검증이 필요합니다. PC 준비 상태 및 단계별 진행 화면 개선은 아직 적용하지 않았습니다.
