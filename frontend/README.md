# MarketCouncil web

React + Vite로 구현한 리서치 열람·사용자 서비스입니다. 분석 엔진은 사용자 PC에서 실행하고, 웹은 저장된 토론과 인용 근거를 읽고 보관·공유합니다.

- `/`: 서비스 소개와 실제 저장된 분석 예시
- `/app`: 공개 리서치 라이브러리와 토론 상세
- `/app?view=my`: 로그인, 내 토론·관심기업·저장한 분석
- `/app?view=admin`: 공식 운영자 전용 성능·RAG·답변 근거 품질 보고서
- `/download`: Windows 프로그램 다운로드와 실행 안내

실제 화면과 시스템 구조는 [프로젝트 README](../README.md)를 참고하세요.

## 로컬 개발

```powershell
cd frontend
npm ci
npm run dev
```

본인 Supabase 프로젝트의 공개 연결 값을 `frontend/.env.local`에 설정합니다.

```env
VITE_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=YOUR_PUBLISHABLE_KEY
```

이 값은 브라우저에서 사용하는 공개 설정입니다. 서버 secret 키·OpenAI 키·OAuth client secret을 넣지 않습니다. 로그인과 개인 보관을 이용하려면 `supabase/`의 관련 스키마·RLS와 Auth 제공자·리다이렉트 URL을 설정해야 합니다. SQL의 적용 순서와 기존 데이터 영향을 검토한 뒤 별도 프로젝트에 준비하세요.

`VITE_RESULTS_BASE_URL`은 기존 공개 JSON 아카이브의 기준 주소입니다. 생략하면 `/data`를 사용합니다. 새 개인 토론은 인증된 사용자 명의로 Supabase에 비공개 저장하고, 소유자가 공유 또는 게시를 선택합니다. 로컬 분석 완료만으로 새 결과가 웹에 자동 공개되지는 않습니다.

## 검사와 배포

```powershell
npm test
npm run build
```

Vercel에는 위 공개 환경 변수와 필요한 공개 아카이브 주소를 설정하고, 검토한 커밋을 배포합니다. 결과 보관·공유는 Supabase를 통해 갱신되므로 결과 하나마다 웹을 재배포할 필요는 없습니다. UI 코드나 빌드 시 주입하는 설정 변경은 다시 배포해야 합니다.

`export_results.py`는 예전 정적 공개 아카이브를 위한 별도 도구입니다. 일상적인 개인 결과 보관에는 마이페이지 JSON 가져오기를 사용합니다. 이 도구의 출력은 공개 자료로 취급되므로 비공개 결과·원문·키를 정적 배포에 포함하지 마세요.

관리자 기록은 허용한 수치·고정 라벨·해시를 검증해 가져오며, 원문을 담은 품질 검토 큐를 업로드하지 않습니다. 사용량 누락은 미측정으로, 사람 정답이 없는 의미 평가는 미평가로 표시합니다. 실제 사용자 화면 렌더링·로그인·DB 권한 검증과 `npm test`의 데이터 계약 검사를 구분해야 합니다.
