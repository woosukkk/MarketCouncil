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
