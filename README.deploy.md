# MarketCouncil 웹 배포

## 준비

`.env.example`을 `.env`로 복사하고 `OPENAI_API_KEY`를 설정합니다. 실제 `.env`는 Git에 포함하지 않습니다.

```env
OPENAI_API_KEY=
DART_API_KEY=
SEC_USER_AGENT=
```

## 실행

```bash
docker compose -f docker-compose.web.yml up --build
```

브라우저에서 `http://localhost:8501`을 엽니다. 앱과 SearXNG는 같은 Docker 네트워크에서 통신합니다.

첫 실행에서는 BGE-M3 모델을 내려받으므로 시간이 오래 걸리고 약 2.3GB 이상의 저장 공간이 필요합니다. 모델, Chroma DB, 분석 결과는 Docker 볼륨에 유지됩니다.

## 배포 전 확인

- 공개 서버에서는 `.env` 대신 배포 플랫폼의 Secret/Environment Variable 기능을 사용합니다.
- 기본 구성은 단일 인스턴스용입니다. 여러 인스턴스로 확장하려면 결과와 벡터 저장소를 외부 영속 스토리지로 옮겨야 합니다.
- 클라우드 배포 대상은 Docker Compose 또는 다중 컨테이너를 지원해야 합니다.
