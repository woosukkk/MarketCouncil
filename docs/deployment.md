# Linux 공개 배포

## 구성과 현재 상태

Streamlit + Python 분석 프로세스 + SearXNG를 한 Linux 서버의 Docker Compose로 실행한다.
Caddy만 80/443 포트를 공개하고, Chroma Cloud에 문서 벡터를 저장한다.
현재 서버/도메인/Chroma Cloud 계정은 준비되지 않았다. 배포 파일 준비는 공개 배포 완료를 뜻하지 않는다.

공개 사용자는 저장된 결과를 열람한다. 새 분석은 ADMIN_TOKEN을 입력한 관리자만 실행할 수 있다.
32자 미만의 키 또는 잘못된 실행 모드에서는 분석을 허용하지 않는다.
단일 서버에서 한 번에 분석 한 개만 실행하며, 서버 재시작 시 실행 중인 분석은 복구되지 않는다.

## 준비

1. Ubuntu Linux 서버와 도메인을 준비한다. BGE-M3와 브라우저 수집기 메모리를 고려해
   RAM 8GB 이상을 초기 검토 기준으로 삼되 실제 분석의 메모리 사용량을 확인하고 조정한다.
   이는 부하 측정 결과나 최소 사양 보장이 아니다.
2. 서버에 Docker Engine과 Compose 플러그인을 설치한다.
3. 도메인의 A 레코드를 서버 IP에 연결한다. 잘못된 AAAA 레코드를 두지 않는다.
4. 80/443을 개방하고 SSH는 관리자의 접속 범위로 제한한다. 8501/8080은 외부에 공개하지 않는다.
5. Chroma Cloud에서 database, tenant, API key를 준비한다. 키는 채팅/저장소에 넣지 않는다.

## 환경 설정

프로젝트 루트에서 `.env.production.example`을 `.env.production`으로 복사한다.
DOMAIN은 scheme/path 없는 실제 도메인이다. ADMIN_TOKEN과 SEARXNG_SECRET은 각각
`python -c "import secrets; print(secrets.token_urlsafe(32))"`로 생성한다.
나머지 API/Chroma 값을 입력하고 `chmod 600 .env.production`을 적용한다.
배포에서는 Compose가 MARKETCOUNCIL_MODE=public, CHROMA_MODE=cloud를 강제한다.
Chroma 설정 누락 시 로컬 DB로 몰래 대체하지 않는다.

## 기존 데이터 이전

분석/문서 색인을 중지하고 로컬 vector_db_bge_m3 폴더를 먼저 백업한다.
로컬 PC의 `.env.production`에 Chroma 연결 값을 설정한 뒤 프로젝트 루트에서:

```powershell
venv\Scripts\python.exe -m tools.migrate_chroma_cloud
```

이 명령은 문서 원문 조각, 메타데이터, 기존 BGE-M3 벡터를 Cloud에 업로드한다.
목적지 컬렉션은 비어 있어야 한다. 기존 기본 L2 컬렉션을 위한 이전 명령이다.
100개씩 복사하고 개수를 대조한다. 검색 품질 검증까지 수행하는 것은 아니다.
중간 실패 시 부분 업로드가 남으므로 새 database에서 다시 실행하거나 목적지 상태를 직접 검토한다.
원본 로컬 DB는 삭제하지 않는다. 이전 도중 색인 작업을 실행하지 않는다.

공개해도 되는 분석 JSON만 서버의 `results/`에 복사한다. 이 디렉터리의 결과는 공개 화면에 표시된다.
분석에 필요한 `documents/`는 별도로 복사한다. Chroma 이전은 PDF 원본/결과 JSON을 이전하지 않는다.
기존 문서 레지스트리에 Windows 절대 경로가 있는 경우 서버에서 재수집/경로 점검이 필요하다.

## 서버 실행

`.env`, venv, 로컬 DB, 키 파일을 제외한 소스와 필요한 데이터만 서버에 전달한다.
프로젝트 루트에서:

```sh
mkdir -p results documents
docker compose --env-file .env.production config --quiet
docker compose --env-file .env.production up -d --build
docker compose --env-file .env.production ps
docker compose --env-file .env.production logs --tail=100 app
```

https://설정한도메인 에 접속해 결과 열람, 비관리자의 분석 차단, 관리자 분석 완료/저장을 확인한다.
첫 분석에는 BGE-M3 다운로드가 필요하며 model_cache 볼륨에 보존된다.
SearXNG는 별도 컨테이너로 실행한다. 앱에 Docker 소켓을 마운트하지 않는다.
Crawl4AI용 Chromium은 앱 이미지에 설치한다.

## 백업과 복구

분석 종료 후 앱을 정지하고 results/documents를 백업한 다음 재시작한다.

```sh
docker compose --env-file .env.production stop app
tar -czf marketcouncil-data-$(date +%F).tar.gz results documents
docker compose --env-file .env.production start app
```

백업은 서버 밖의 보관 장소에도 복사하고 복원 검증한다. 환경 비밀값은 별도 안전한 장소에 보관한다.
Chroma 데이터 백업/내보내기는 별도로 관리한다. 로컬 원본 DB 백업을 유지한다.
복원은 앱 정지 상태에서 프로젝트 루트에 results/documents를 풀고 다시 시작한다.
`docker compose down -v`는 모델/인증서 볼륨을 삭제하므로 일반 업데이트에 사용하지 않는다.

## 검증 범위와 제한

실제 Linux 이미지 빌드, Chroma 연결/데이터 이전, HTTPS 발급, 유료 API를 사용한 전체 분석은
서버/계정 준비 후 검증해야 한다. Docker 엔진이 꺼진 현재 PC에서는 이미지 빌드를 확인하지 못했다.
서버 의존성은 SearXNG Python 패키지를 제외한다(별도 컨테이너로 실행).
Streamlit 버전은 로컬 검증 버전으로 고정하고, 나머지는 첫 성공 빌드 후 운영 버전 잠금을 권장한다.

로컬 검증: `python -m unittest tests.test_deployment tests.test_web_analysis_runner tests.test_debate_web` 11개 통과.
Compose 변수 보간/환경 파일 로딩을 제외한 구성 검증과 수정 Python 파일 8개의 구문 검증 통과.
