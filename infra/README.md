# infra

로컬 LIVE용 Docker Compose입니다. Redis, Kafka, Kubernetes는 포함하지 않습니다. 인증이 없으므로 호스트 포트는 `127.0.0.1`만 엽니다.

저장소 루트:

```powershell
.\scripts\doctor-live.ps1
.\scripts\run-live.ps1
.\scripts\stop-live.ps1
```

같은 파일을 직접 쓸 때:

```powershell
docker compose -f infra/docker-compose.yml up --build -d
docker compose -f infra/docker-compose.yml down
```

`down`은 볼륨을 지우지 않습니다. 볼륨 삭제는 `.\scripts\stop-live.ps1 -Volumes`처럼 명시할 때만 합니다.

- `postgres`: PostgreSQL 16. 호스트 포트는 `127.0.0.1:5432`만 엽니다. healthcheck는 `pg_isready`입니다.
- `backend`: Spring Boot API. 컨테이너 안에서는 `0.0.0.0:8080`으로 듣고, 호스트에는 `127.0.0.1:8080`만 게시합니다. healthcheck는 `GET /api/v1/health`입니다. `fixtures/trusted-projects`를 `/trusted`로, `maidops-models`를 `/models`로 붙입니다.
- `worker`: 등록된 `{python}` argv만 실행합니다. 같은 `/trusted`를 보고, alive 파일 `/tmp/maidops-worker-alive`로 프로세스 healthcheck를 합니다. API에는 루프마다 `POST /api/v1/worker/heartbeat`를 보냅니다.
- `trainer`: CPU로 학습합니다. 같은 `maidops-models`를 `/models`로 보고, alive 파일 `/tmp/maidops-trainer-alive`로 프로세스 healthcheck를 합니다. 대기 중에도 `POST /api/v1/trainer/heartbeat`를 보냅니다.

데이터베이스 사용자와 비밀번호 `maidops`는 이 로컬 Compose 전용 기본값입니다.

`GET /api/v1/health`는 `database`, `worker`, `trainer`를 구분합니다. 풀스택이 heartbeat를 보내고 있으면 `worker=CONNECTED`, `trainer=CONNECTED`입니다. 백엔드만 켜면 둘 다 `NOT_CONNECTED`가 맞습니다. Compose의 컨테이너 healthcheck는 alive 파일이고, API의 CONNECTED는 최근 DB heartbeat입니다. 둘은 같은 파일이 아닙니다.

빌드 컨텍스트는 `backend/Dockerfile`, `worker/Dockerfile`, `trainer/Dockerfile`입니다. 별도 레지스트리 이미지는 쓰지 않습니다.

`infra/isolated`는 감사용 설정입니다. 기본 LIVE 기동은 그 파일을 사용하지 않습니다.
