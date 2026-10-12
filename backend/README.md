# backend

PHASE 2 API입니다. Java 21, Spring Boot 3.5.16, Flyway, PostgreSQL을 사용합니다. 버전 근거는 `docs/ARCHITECTURE.md`에 있습니다.

이 프로세스는 등록된 작업을 셸로 실행하지 않습니다. `POST /api/v1/jobs`는 작업을 `QUEUED`로 저장합니다. 실행은 `worker/`가, MLP 학습은 `trainer/`가 담당합니다. 조건이 부족한 학습은 행을 만들지 않습니다. 서버는 모델 파일을 PyTorch로 열지 않고 체크섬만 확인합니다.

## Windows에서 테스트

```powershell
$env:JAVA_HOME = "C:\Program Files\Java\jdk-21"
$env:Path = "$env:JAVA_HOME\bin;" + $env:Path
.\mvnw.cmd -B test
```

`backend` 디렉터리에서 실행합니다. 테스트는 내장 PostgreSQL을 내려 받아 띄웁니다. Docker는 필요 없습니다. 이 PC에는 `C:\Program Files\Java\jdk-21`이 없으므로, 그 경로가 없으면 이미 설치된 JDK 21을 `JAVA_HOME`으로 둔 뒤 같은 명령을 실행합니다.

## 실행

권장 경로는 저장소의 `infra/docker-compose.yml`입니다. 호스트에서만 실행할 때는 JDK 21과 `127.0.0.1:5432`의 PostgreSQL이 필요하고, 기본 계정은 로컬 전용 `maidops` / `maidops`입니다.

```powershell
$env:JAVA_HOME = "C:\Program Files\Java\jdk-21"
.\mvnw.cmd -B spring-boot:run
```

기본 바인딩은 `127.0.0.1:8080`입니다. 인증이 없으므로 이 주소를 외부에 열지 않습니다.

상태 확인: `GET /api/v1/health` 와 `GET /actuator/health`.
