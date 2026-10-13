# 재현

모든 Compose 명령은 프로젝트 이름과 파일을 지정했다. 비밀번호는 `[REDACTED]`로 적는다. 실제 값은 격리 Compose의 로컬 기본 계정이며 사용자 DB 비밀번호가 아니다.

기존 `infra/docker-compose.yml`은 기동하지 않았다. `down --volumes`와 `docker system prune`은 하지 않았다.

## 이미지

이미 있던 이미지: `postgres:16-alpine`.  
새로 빌드한 이미지: `maidops-isolated-backend`, `maidops-isolated-worker`, `maidops-isolated-trainer`.

빌드 중 받은 것:

- backend 이미지의 JDK 베이스와 Maven 의존성
- worker·trainer의 `python:3.11-slim`
- trainer의 CPU용 `torch==2.14.1` (`download.pytorch.org` CPU 인덱스)

모델 가중치나 외부 프로젝트는 받지 않았다. 이전 `infra-*` 이미지는 사용하지 않았다.

```text
docker compose --project-name maidops-isolated -f infra/isolated/docker-compose.yml build
```

## 기동

```text
powershell -File scripts/check-isolated-compose.ps1
docker compose --project-name maidops-isolated -f infra/isolated/docker-compose.yml up -d postgres
```

Postgres가 준비된 뒤 격리 서버 안에서 데이터베이스 두 개를 만들었다.

```text
CREATE DATABASE maidops_live_audit;
CREATE DATABASE maidops_upgrade_audit;
```

백엔드는 `maidops_live_audit`만 바라본다. 이 변경은 `infra/isolated/docker-compose.yml`의 데이터소스 URL이다. 기본 데이터베이스 이름이 `maidops_isolated`로 남아 있으면 백엔드가 빈 감사 DB에 붙지 않아서 바꿨다. 워커 id는 `MAIDOPS_WORKER_ID=audit-worker-1`로 고정했다. 재시작 뒤에도 같은 id로 늦은 요청을 보내기 위해서다.

## V6와 업그레이드

현재 backend를 V6 DB에 붙여 최신 migration이 자동으로 이어지지 않게, 일회성 컨테이너만 사용했다.

```text
docker compose --project-name maidops-isolated -f infra/isolated/docker-compose.yml run --no-deps --name maidops-isolated-flyway-v6 -e SPRING_DATASOURCE_URL=jdbc:postgresql://postgres:5432/maidops_upgrade_audit -e SPRING_FLYWAY_TARGET=6 backend
```

로그: migration 6개 적용, 버전 v6. 이어서 Hibernate가 `log_storage_incomplete` 없음으로 기동을 거부했다. history는 6에서 멈췄다.

그 다음 `job-upgrade-audit`, `case-upgrade-audit`, revision, `res-upgrade-audit`를 넣었다. raw SHA-256은 `a523152b07345189224ab82a5517ddc745430864ea3ffe1915a5cefb20681bea`.

```text
docker compose --project-name maidops-isolated -f infra/isolated/docker-compose.yml run -d --no-deps --name maidops-isolated-flyway-latest -e SPRING_DATASOURCE_URL=jdbc:postgresql://postgres:5432/maidops_upgrade_audit backend
```

로그: 버전 6에서 7, 8로 올라가고 validate 8건, 앱 기동. 재시작 뒤 `No migration necessary`. fixture SHA와 승인 상태, 해결 원인은 그대로였다.

이 일회성 앱은 호스트 18080을 열지 않았다. 확인 후 `docker stop maidops-isolated-flyway-latest`.

## 본 스택

```text
docker compose --project-name maidops-isolated -f infra/isolated/docker-compose.yml up -d backend worker trainer
```

API 절차는 `infra/isolated/live_audit.py`, `live_audit_followup.py`, `live_audit_trim.py`에 있다. 호스트 Python 3.11로 18080만 호출했다.

감사 fixture는 `fixtures/trusted-projects/sample`을 `infra/isolated/workspace/sample`로 복사하고, `tick_check.py`, `trim_check.py`, `flood_check.py`, `hang_check.py`, `tree_check.py`를 추가했다. 등록은 `maidops_live_audit.registered_tasks`에만 했다. `audit-trim`의 timeout은 60초로 바꿨다. 20초로는 500줄을 서버에 보내기 전에 타임아웃이 났다.

## 종료

```text
docker compose --project-name maidops-isolated -f infra/isolated/docker-compose.yml stop
```

볼륨은 지우지 않았다.
