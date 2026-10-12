# infra

PHASE 2 로컬 실행용 Docker Compose입니다. Redis, Kafka, Kubernetes는 포함하지 않습니다.

```powershell
docker compose -f infra/docker-compose.yml up --build
```

저장소 루트에서 실행합니다.

- `postgres`: PostgreSQL 16. 호스트 포트는 `127.0.0.1:5432`만 엽니다. healthcheck는 `pg_isready`입니다.
- `backend`: Spring Boot API. 컨테이너 안에서는 `0.0.0.0:8080`으로 듣고, 호스트에는 `127.0.0.1:8080`만 게시합니다. healthcheck는 `GET /api/v1/health`입니다.

데이터베이스 사용자와 비밀번호 `maidops`는 이 로컬 Compose 전용 기본값입니다. 인증 없는 API이므로 포트를 외부 인터페이스에 게시하지 않습니다.

API가 준비되면 `worker` 필드는 `NOT_CONNECTED`입니다. 그건 장애가 아니라, 실행 워커를 이 단계에서 두지 않았다는 표시입니다.
