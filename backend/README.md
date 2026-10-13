# backend

PHASE 2 API입니다. Java 21, Spring Boot 3.5.16, Flyway, PostgreSQL을 사용합니다. 버전 근거는 `docs/ARCHITECTURE.md`에 있습니다.

이 프로세스는 등록된 작업을 셸로 실행하지 않습니다. `POST /api/v1/jobs`는 작업을 `QUEUED`로 저장합니다. 실행은 `worker/`가, MLP 학습은 `trainer/`가 담당합니다. 조건이 부족한 학습은 행을 만들지 않습니다. 서버는 모델 파일을 PyTorch로 열지 않고 체크섬만 확인합니다.

## Windows에서 테스트

저장소 루트에서 `..\scripts\test-backend.ps1`을 실행합니다. 스크립트는 `java`와 `javac`가 모두 21인 JDK를 고르고 Maven Wrapper로 테스트한 뒤 `JAVA_HOME`과 PATH를 되돌립니다. 폴더 이름이 `jdk-21`이 아니어도 됩니다.

```powershell
..\scripts\test-backend.ps1
```

`backend` 디렉터리에서 직접 실행할 때는 그 JDK를 `JAVA_HOME`으로 둔 뒤 `.\mvnw.cmd -B test`를 실행합니다. 테스트는 내장 PostgreSQL을 사용합니다. Docker는 필요 없습니다.

## 실행

권장 경로는 저장소의 `infra/docker-compose.yml`입니다. 호스트에서만 실행할 때는 JDK 21과 `127.0.0.1:5432`의 PostgreSQL이 필요하고, 기본 계정은 로컬 전용 `maidops` / `maidops`입니다.

호스트에서 서버를 띄울 때는 JDK 21을 `JAVA_HOME`으로 둔 뒤 `.\mvnw.cmd -B spring-boot:run`을 실행합니다. `scripts/test-backend.ps1 -ResolveOnly`로 그 JDK 경로를 확인할 수 있습니다.

기본 바인딩은 `127.0.0.1:8080`입니다. 인증이 없으므로 이 주소를 외부에 열지 않습니다.

상태 확인: `GET /api/v1/health` 와 `GET /actuator/health`.
