# Windows 0.6.0 상세 계측 배포 검증

검증일: 2026-10-29. 관련 이슈: https://github.com/woosukkk/MarketCouncil/issues/25

## 변경 목적

웹 관리자 화면은 단계별 시간과 API 사용량을 읽지만 기존 0.5.0 다운로드는 전체 시간만 수집했다. 상세 수집기를 포함한 0.6.0 패키지와 단가 JSON을 배포해 새 로컬 분석에서 같은 형식의 기록을 만들도록 연결한다. 원문·프롬프트·API 키는 보고서에 남기지 않는다.

프로그램의 기본 동작과 데이터 저장·공개 권한을 바꾸지 않는다. 상세 기록은 로컬 metrics에만 생성되며 원격 전송은 관리자의 파일 가져오기 선택으로 실행한다. 이전 시간 기록은 계속 읽으며 과거 실행의 토큰과 비용을 소급 생성하지 않는다. 비용은 관측 응답의 날짜별 단가 추정이고 SDK 내부 재시도·별도 도구 요금·실제 계정 청구액이 아니다.

## 검증 범위

- Python 129개와 웹 48개 검사 통과, Vite 프로덕션 빌드 성공. 이전 검증과 중복된 검사를 고유 검사 수에 더하지 않는다.
- 현재 작업과 관계없는 미커밋 수정은 그대로 두고 실제 커밋의 git archive 스냅샷에서 빌드했다.
- 자체 검사에 합성 응답을 사용한 실제 수집기 실행을 추가했다. 실제 SDK 호출 없이 단계·API 요청 수·토큰·단가·비용·버전과 프롬프트 제외 여부를 검증한다. 합성 계측은 서비스 성능이나 실제 API 사용량의 벤치마크가 아니다.

## 적용 방법과 제한

새 ZIP을 별도 폴더에 풀고 `_internal`을 유지한다. 자동 게시를 사용하는 운영자는 새 폴더에서 설정을 다시 저장해 예약 경로를 갱신한다. 기존 사용자 데이터와 예약 작업은 이번 배포에서 자동 변경하지 않는다.

새 유료 분석·공식 게시·실제 계정 업로드·EXE 예약 등록·별도 PC의 전체 분석은 검증하지 않았다. 가용 메모리가 약 0.9GB여서 실제 RAG 모델 재측정은 시작하지 않았다. 의미 품질의 사람 정답 검수도 별도 후속 작업이다.


## 실제 검증 결과와 공개 확인

- Windows 0.6.0 ZIP: 462,819,571 bytes, 9,816개 항목. CRC·필수 리소스·빌드 메타데이터·동봉 단가의 일치를 확인했다.
- SHA-256: `49d4fff8e5dc9324e99bc6918a3a74408f8ad3e070677acd0e30eb4687ee675a`. GitHub 자산 digest와 공개 SHA256.txt가 일치하고 공개 ZIP HEAD와 체크섬 GET이 200이었다. ZIP 본문을 다시 내려받지는 않았다.
- ZIP을 푼 EXE를 별도 프로필에서 실행해 GUI 버튼 생성·워크플로·브라우저 드라이버·Crawl4AI 리소스 초기화와 합성 단계/API 토큰/단가 기록 검사를 종료 코드 0으로 완료했다. 소요 시간 32.802초는 이번 초기화·합성 검사 1회의 시간이며 전체 분석 성능이나 시작 속도의 개선율이 아니다.
- 공개 /, /app?view=admin, /download와 실제 /assets/index-C-3SVNg6.js에서 0.6.0 ZIP 링크·상세 계측 안내·기존 answer_quality/by_phase를 확인했다. 공개 SPA와 번들의 HTTP 검사이며 실제 계정의 화면 조작·DB 읽기/쓰기는 수행하지 않았다.

## 배포 정보

- 실제 빌드 커밋: `ba1c20d2235b3d7015350409fadeae9d6e580814`
- Windows: https://github.com/woosukkk/MarketCouncil/releases/tag/desktop-v0.6.0
- Web: https://frontend-okye0n5e9-woosukk.vercel.app
- 운영: https://frontend-six-pi-h5i7tztups.vercel.app/download
- Vercel: dpl_8DrSig2TpDDgFU9E6PMQiaKQH5XB
- 버전: desktop-v0.6.0, web-v0.12.1. 기존 0.5.0 자산은 유지했다.

웹은 --skip-domain으로 먼저 준비했고 보호된 준비 URL은 CLI 인증으로 검증했다. Vercel CLI가 인증 읽기에 사용하는 protection bypass token을 생성했으며 값은 로컬 CLI 설정에서만 취급했다. 일반 사용자 권한·Supabase RLS를 변경하지 않았다. 공개 ZIP 검증 후 운영 주소를 전환했다.
