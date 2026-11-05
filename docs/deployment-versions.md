# 배포 버전 기록

웹은 web-vX.Y.Z, Windows 프로그램은 desktop-vX.Y.Z로 별도 관리합니다.
기존 기록을 확인하여 사후 태그를 등록했습니다. 아래 시각은 배포 생성 시각(한국 시간)입니다.
Vercel의 gitDirty=1 표시 때문에 태그는 배포 메타데이터의 기준 커밋을 가리키며, 당시 업로드된 모든 파일과 일치함을 보장하지 않습니다.
커밋되지 않은 배포 변경의 정확한 내용은 현재 기록만으로 복원하지 않았습니다.

| 버전 | 배포 시각 (KST) | 기준 커밋 | 배포 주소 |
| --- | --- | --- | --- |
| web-v0.1.0 | 2026-10-08T20:39:15+09:00 | 52ceac6 | https://frontend-1wdyhcgun-woosukk.vercel.app |
| web-v0.1.1 | 2026-10-08T21:24:09+09:00 | 52ceac6 | https://frontend-dayc67zqn-woosukk.vercel.app |
| web-v0.2.0 | 2026-10-08T21:35:46+09:00 | 9ddc811 | https://frontend-ma876fa90-woosukk.vercel.app |
| web-v0.2.1 | 2026-10-08T21:39:50+09:00 | 6f102db | https://frontend-p3za2oo30-woosukk.vercel.app |
| web-v0.3.0 | 2026-10-09T20:38:08+09:00 | 90665d6 | https://frontend-cbz55qtpg-woosukk.vercel.app |
| web-v0.4.0 | 2026-10-09T20:52:49+09:00 | f9b01d5 | https://frontend-dczl086w6-woosukk.vercel.app |
| web-v0.5.0 | 2026-10-09T22:16:19+09:00 | 8ab6211 | https://frontend-8klx8pbu7-woosukk.vercel.app |
| web-v0.5.1 | 2026-10-09T22:24:39+09:00 | 89d3e62 | https://frontend-i92y8l15l-woosukk.vercel.app |

## Windows 프로그램

- desktop-v0.1.0: 기존 태그를 유지합니다. 당시 태그는 master의 과거 커밋을 가리키므로 배포 소스 기록으로 사용할 수 없습니다.
- desktop-v0.1.1: ce61646, 기업명 자동 종목 조회가 반영된 현재 소스.
- 현재 실행 파일은 기존 desktop-v0.1.0 릴리스의 다운로드 주소에 있습니다. 이전 0.1.0 바이너리는 교체되어 별도 보관되지 않았습니다.
- 현재 바이너리 SHA256: 1e40027dad2c9d59ed5b6f60d7616b752681650793c11270c5e28218d20d9aa9.
- 로컬 작업 중 파일이 있었으므로, 바이너리 전체가 태그 소스만으로 동일 재현된다고 보장하지 않습니다.

## 앞으로 배포할 때

1. 승인된 변경만 커밋하고 깨끗한 작업 트리에서 빌드합니다.
2. 웹/데스크톱별 버전을 올립니다. 기능 추가는 minor, 수정은 patch를 올립니다.
3. 배포 성공과 필요한 검증을 확인한 뒤 실제 빌드 커밋에 annotated tag를 붙입니다.
4. 태그를 GitHub에 푸시하고 배포 URL, 변경 사항, 검증 결과, 제한을 릴리스에 기록합니다.
5. 실행 파일은 새 버전 릴리스에 별도 첨부하고 이전 버전 자산을 덮어쓰지 않습니다.
6. 배포하지 않은 코드 변경은 배포 버전으로 기록하지 않습니다.

Railway의 과거 배포는 이번에 정확한 배포 커밋/시각 기록을 확인하지 못해 태그를 추정해서 만들지 않았습니다.


## 2026-10-27 검증 배포

| 버전 | 실제 빌드 커밋 | 배포 주소 |
| --- | --- | --- |
| desktop-v0.5.0 | b9f2f87e65d27f944c79b7813c28206519e00826 | https://github.com/woosukkk/MarketCouncil/releases/tag/desktop-v0.5.0 |
| web-v0.11.0 | b9f2f87e65d27f944c79b7813c28206519e00826 | https://frontend-m12kpx7qw-woosukk.vercel.app |

현재 공개 다운로드는 desktop-v0.5.0의 MarketCouncil-Windows.zip입니다. 위 Windows 프로그램 절의 0.1.x 현재 파일·해시 설명은 과거 기록입니다. 0.4.0 릴리스 자산은 유지했습니다.

검증한 커밋의 git archive 스냅샷에서 빌드해 기존 미커밋 작업을 포함하지 않았습니다. 웹의 운영 주소는 https://frontend-six-pi-h5i7tztups.vercel.app 이며, Vercel 배포 dpl_GAAWK2MqLR8aJxACQN774HPxAAqM의 프로덕션 연결과 공개 페이지 응답을 확인했습니다. 두 버전은 annotated tag로 실제 빌드 커밋을 가리킵니다. 상세 검증과 제한은 release-verification-2026-10-27.md 및 이슈 #23을 참조합니다.


## 2026-10-28 관리자 측정 배포

- web-v0.12.0: 0918b6e8255c9ce44e8f8682e7ab949e8ca87432
- 배포 주소: https://frontend-5akd9zjnw-woosukk.vercel.app
- 운영 주소: https://frontend-six-pi-h5i7tztups.vercel.app/app?view=admin
- Vercel 배포: dpl_7xhd1fqxmiFxU3TzGvwx9vyBTBDt, READY와 기존 운영 주소 연결 확인.
- 단계/API 토큰 관측과 답변 근거 품질 관리자 탭을 배포했다. 기존 Windows 다운로드 desktop-v0.5.0은 유지한다. 상세 수집은 최신 소스 실행부터 지원하며 이번에 새 Windows 패키지를 만들지 않았다.
- 깨끗한 커밋 스냅샷을 배포했고 공개 /, /app?view=admin, /download 및 실제 JS index-BRrqQEMN.js 응답과 새 기능 문구를 확인했다.

## 2026-10-29 Windows 상세 계측 배포

| 버전 | 실제 빌드 커밋 | 배포 주소 |
| --- | --- | --- |
| desktop-v0.6.0 | ba1c20d2235b3d7015350409fadeae9d6e580814 | https://github.com/woosukkk/MarketCouncil/releases/tag/desktop-v0.6.0 |
| web-v0.12.1 | ba1c20d2235b3d7015350409fadeae9d6e580814 | https://frontend-okye0n5e9-woosukk.vercel.app |

현재 다운로드는 0.6.0이며 0.5.0의 기존 자산은 유지한다. 새 Windows 분석부터 상세 단계·API 관측·토큰 비용 추정 JSON을 생성한다. 실제 ZIP/EXE·공개 SHA-256·웹 운영 주소와 번들을 확인했다. Vercel 배포는 dpl_8DrSig2TpDDgFU9E6PMQiaKQH5XB이며 운영 주소는 https://frontend-six-pi-h5i7tztups.vercel.app 이다. 두 annotated tag는 실제 빌드 커밋을 가리킨다. 실제 유료 분석·EXE 예약 등록·다른 PC 전체 실행은 검증하지 않았다. 자세한 결과는 release-verification-2026-10-29.md 및 이슈 #25에 기록했다.


## 2026-11-03 웹 한영 전환 배포

- web-v0.13.0: `0323f210d26b7787be2d4c7b2a30bca2ffaac97e`
- 배포 주소: https://frontend-azflc9zsf-woosukk.vercel.app
- 운영 주소: https://frontend-six-pi-h5i7tztups.vercel.app
- Vercel 배포: `dpl_4gUQPuxjojoucv4GNzryYcF1arV2`, READY와 운영 별칭 연결 확인.
- 소개·리서치·다운로드 오른쪽 위 언어 전환, 선호 저장과 영문 UI를 배포했다. 분석 본문·인용은 원문을 유지하며 Windows 0.6.0 다운로드는 그대로 사용한다.
- 최종 웹 테스트 55개와 빌드가 통과한 커밋의 깨끗한 스냅샷을 배포했다. 공개 세 경로와 실제 JS 번들 응답, 운영 브라우저 전환·기존 로그인 상태 유지를 확인했다. 상세 범위와 제한은 [한영 전환 검증](web-language-2026-11-03.md) 및 이슈 #27에 기록했다.


## 2026-11-03 다기업 Windows 다운로드 배포

| 버전 | 실제 빌드 커밋 | 배포 주소 |
| --- | --- | --- |
| desktop-v0.7.0 | 8a15dcd8e1d26d91ec9bfd1ac303dc4bc9836c38 | https://github.com/woosukkk/MarketCouncil/releases/tag/desktop-v0.7.0 |
| web-v0.13.1 | 8a15dcd8e1d26d91ec9bfd1ac303dc4bc9836c38 | https://frontend-60iybme2q-woosukk.vercel.app |

공개 다운로드를 0.7.0으로 전환했다. 기존 0.6.0 자산은 유지한다. 깨끗한 커밋 스냅샷에서 Python 126개·웹 57개와 빌드를 통과했고, 실제 ZIP/EXE·공개 digest/체크섬과 운영 주소·번들을 확인했다. Vercel 배포는 dpl_C3biXzbTdHE1obQDJE4P4MBB9aFG다. 다기업 조회·재무 공급과 저장 분리는 확인했으며 새 유료 AI 토론 품질·별도 PC 전체 실행은 검증하지 않았다. 자세한 결과는 [0.7.0 배포 검증](release-verification-2026-11-03-v070.md) 및 이슈 #28을 참고한다.


## 2026-11-05 기업별 근거 준비·공식 선정 배포

| 버전 | 실제 빌드 커밋 | 배포 주소 |
| --- | --- | --- |
| desktop-v0.8.0 | 40d0a3d5fe1e2a3c7a755297f98f4fa73d6353ae | https://github.com/woosukkk/MarketCouncil/releases/tag/desktop-v0.8.0 |
| web-v0.14.0 | 40d0a3d5fe1e2a3c7a755297f98f4fa73d6353ae | https://frontend-c6qo0d7tk-woosukk.vercel.app |

6기업 선택·관리자 근거 현황과 Windows 원문 준비/gate/공식 선택을 적용했다. 사용자 요청으로 전체 테스트는 보류하고 프로덕션 빌드·패키지 초기화·공개 화면을 확인했다. 미국 2기업은 SEC 공시 접근 제한이 남아 있어 최소 자료 미달로 차단한다. 상세 범위와 보류 항목은 [0.8.0 배포 기록](release-verification-2026-11-05-v080.md) 및 #29에 기록했다.


## 2026-11-05 발행사 원문·기업 관계·공통 평가 화면

| 버전 | 실제 빌드 커밋 | 배포 주소 |
| --- | --- | --- |
| desktop-v0.8.1 | ac19ff88d88578d13e66fbaa17eb248eaef160eb | https://github.com/woosukkk/MarketCouncil/releases/tag/desktop-v0.8.1 |
| web-v0.15.0 | 3c9200fd2c1b927f673e9c436cc9e7cc0da36a76 | https://frontend-bdtixb4e5-woosukk.vercel.app |

SEC 실패 시 발행사 원문으로 수집을 이어가고 웹에 출처 기반 관계 지도 및 관리자 공통 평가 기준을 적용했다. 실제 분석·새 테스트·벤치마크·EXE 실행은 사용자 요청으로 보류했다. 빌드/배포 반영과 패키지 무결성만 확인했다. 상세 범위와 남은 제한은 [배포 기록](release-verification-2026-11-05-v081.md)과 #31에 남긴다.
