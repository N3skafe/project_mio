# MaidOps Lab

터미널 안에서 동작하는 개발 조수입니다. 오리지널 고양이 수인 메이드가 작업 상태를 설명하고, 실제 업무 판단은 서비스 계층이 담당합니다.

현재 구현은 **PHASE 9**입니다. DEMO는 Java와 데이터베이스 없이 그대로 동작하고 학습하지 않습니다. LIVE는 Spring Boot API, PostgreSQL, 등록 명령 워커, 학습기를 사용합니다. 신뢰하는 workspace 안에 자기 프로젝트와 `{python}` 작업을 등록할 수 있고, 이미 나온 실패 로그를 실행 없이 오류 사례로 가져올 수 있습니다. 실패 로그의 라벨 초안은 기본 모델이 없으면 규칙 기반이고, 있으면 모델 초안입니다. 확정된 라벨이 조건을 만족하면 `trainer/`가 고정 해시 임베딩과 작은 MLP를 학습합니다. 워커가 없으면 새 작업은 `QUEUED`로 남고, 성공으로 바뀌지 않습니다. 외부 LLM, 유료 임베딩 API, 임의 셸, 자동 코드 수정은 없습니다. 비슷한 실패는 확정 기록을 로컬 해시 코사인으로 찾고, 그 기록만 인용합니다.

## DEMO와 LIVE

| 모드 | 의미 |
| --- | --- |
| DEMO | 고정 fixture로 가상 작업을 재생합니다. 셸, 프로젝트 파일, 네트워크, 모델에 접근하지 않습니다. 화면의 연결 상태는 `DEMO(가상, 백엔드 없음)`입니다. 세션 데이터는 종료하면 사라집니다. |
| LIVE | `ApiService`가 `MAIDOPS_BACKEND_URL`로 백엔드에 접속합니다. 연결되면 작업, 검토, 해결 기록, 학습 실행, 프로젝트 등록, 실패 로그 가져오기가 PostgreSQL에 남습니다. 연결에 실패하면 `DISCONNECTED`와 실패 원인을 보여 주고 작업을 만들지 않습니다. |

인증은 없습니다. API는 localhost 단일 사용자용이며 외부에 노출하지 않습니다. Compose는 호스트 포트를 `127.0.0.1`에만 엽니다.

## DEMO 설치와 실행

Python 3.11이 필요합니다. 이 환경에서는 `py -3.11`로 확인한 버전이 3.11.9입니다. DEMO만 쓸 때는 Docker와 Java가 필요 없습니다.

```powershell
cd tui
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m maidops_tui
```

테스트:

```powershell
cd tui
.\.venv\Scripts\python -m pytest
```

리포지토리 루트에서:

```powershell
.\scripts\test-tui.ps1
.\scripts\run-tui.ps1
```

스크립트는 이미 만든 `.venv`를 사용합니다. 설치 명령은 위의 `pip install`입니다.

한글이 깨지면 Windows Terminal에서 UTF-8을 사용합니다.

```powershell
chcp 65001
```

Linux에서는 같은 순서를 `python3.11 -m venv .venv`와 `source .venv/bin/activate`로 실행할 수 있게 작성했습니다. 이 개발 환경에서는 Linux 실행을 확인하지 않았습니다.

선택 설정은 환경 변수입니다. 예시는 `.env.example`에 있습니다. 비밀 값은 넣지 않습니다. DEMO는 `MAIDOPS_BACKEND_URL`에 접속하지 않습니다.

```powershell
$env:MAIDOPS_MODE = "DEMO"
$env:MAIDOPS_CHARACTER_NAME = "미오"
$env:MAIDOPS_QUIET = "false"
```

## LIVE 실행

DEMO 다음에 LIVE를 쓰려면 저장소 루트에서 한 명령을 씁니다. Compose는 `postgres`, `backend`, `worker`, `trainer`를 함께 띄웁니다. 호스트 포트는 `127.0.0.1:5432`와 `127.0.0.1:8080`만 엽니다.

```powershell
.\scripts\doctor-live.ps1
.\scripts\run-live.ps1
```

`run-live.ps1`은 Docker와 Compose를 확인한 뒤 `docker compose -f infra/docker-compose.yml up --build -d`를 실행하고, health가 `database=UP`, `worker=CONNECTED`, `trainer=CONNECTED`가 될 때까지 기다립니다. 준비되면 다음 명령을 출력합니다. TUI까지 이어서 띄우려면 `.\scripts\run-live.ps1 -WithTui` 입니다. 중지는 `.\scripts\stop-live.ps1` 이고 볼륨은 유지합니다. 볼륨까지 지우려면 `.\scripts\stop-live.ps1 -Volumes` 를 명시해야 합니다.

풀스택이 준비된 health 예:

```text
database=UP
worker=CONNECTED
trainer=CONNECTED
authentication=NONE
```

백엔드만 켜고 워커와 학습기 프로세스가 없으면 `worker=NOT_CONNECTED`, `trainer=NOT_CONNECTED`가 맞습니다. 그건 장애가 아니라 프로세스가 없다는 표시입니다. Compose healthcheck는 컨테이너 안 alive 파일이고, API health는 최근 20초 heartbeat입니다.

첫 샘플은 TUI LIVE에서 아래 순서입니다.

```text
/project list
/project select trusted-sample
/test
```

실행 없이 로그 1건만 남기려면:

```text
/import-log trusted-sample Connection to localhost:5432 refused
```

같은 스택을 직접 띄우는 명령은 다음과 같습니다.

```powershell
docker compose -f infra/docker-compose.yml up --build -d
```

2026-11-10 확인에서 Docker CLI 29.8.2와 Compose v5.6.0은 있고, `docker compose config`는 통과했습니다. 데몬이 떠 있지 않아 `up`은 실행하지 않았습니다. 스크립트와 문서는 그 기동과 별개로 준비되어 있습니다. Compose의 데이터베이스 비밀번호 `maidops`는 로컬 전용 기본값입니다.

```powershell
cd tui
$env:MAIDOPS_MODE = "LIVE"
$env:MAIDOPS_BACKEND_URL = "http://127.0.0.1:8080"
.\.venv\Scripts\python -m maidops_tui
```

백엔드를 호스트에서 직접 실행하려면 JDK 21과 PostgreSQL이 필요합니다. 기본 `JAVA_HOME`이 JDK 11이어도 `scripts/test-backend.ps1`이 `JavaHome`, `JAVA_HOME`, PATH, 설치된 JDK 디렉터리에서 `java`와 `javac`가 모두 21인 경로를 고릅니다. 폴더 이름이 `jdk-21`일 필요는 없습니다. 스크립트는 Maven Wrapper를 쓰고, 끝난 뒤 프로세스의 `JAVA_HOME`과 PATH를 되돌립니다.

```powershell
.\scripts\test-backend.ps1
```

저장소 루트에서 위 명령을 실행합니다. 통합 테스트는 Docker 없이 내장 PostgreSQL을 사용합니다.

학습기는 별도 프로세스입니다. CPU 휠을 설치하고, 백엔드와 같은 `MAIDOPS_MODEL_DIR`를 씁니다. 문장 벡터는 로컬 해시라서 모델 파일을 받지 않습니다.

```powershell
cd trainer
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]" --extra-index-url https://download.pytorch.org/whl/cpu
$env:MAIDOPS_BACKEND_URL = "http://127.0.0.1:8080"
$env:MAIDOPS_MODEL_DIR = "..\data\models"
$env:MAIDOPS_TRAIN_DEVICE = "auto"
$env:MAIDOPS_CODE_ROOT = ".."
.\.venv\Scripts\python -m maidops_trainer
```

저장소 루트에서는 `.\scripts\run-trainer.ps1`과 `.\scripts\test-trainer.ps1`을 사용합니다. 이 개발 PC에 설치된 휠은 `torch 2.14.1+cpu`라서 CUDA 학습은 실행하지 않았습니다. `MAIDOPS_TRAIN_DEVICE=cuda`인데 CUDA가 없으면 CPU로 바꾸지 않고 학습을 실패로 남깁니다.

API는 인증이 없습니다. `server.address` 기본값은 `127.0.0.1`입니다. Compose 안에서는 컨테이너가 `0.0.0.0`으로 듣고, 호스트 포트는 `127.0.0.1:8080`에만 게시됩니다.

LIVE Workspace에서 `trusted-sample`을 고르면 작업 목록에 실패 시나리오 50개가 있습니다. 라벨마다 문장이 다른 로그 10개입니다. 하나를 고른 뒤 테스트 실행을 누르면 그 등록 명령만 실행됩니다. 초안을 승인하거나 수정해 확정 라벨이 조건을 넘으면 Lab에서 학습을 시작할 수 있습니다. 프로젝트를 바꾸면 선택은 그 프로젝트의 기본 작업으로 돌아갑니다.

## 단축키

| 키 | 동작 |
| --- | --- |
| F1 | 도움말 |
| F2 | Workspace |
| F3 | Review |
| F4 | Lab |
| F5 | History |
| Ctrl+L | 명령 입력창으로 포커스 |
| Ctrl+Q | 종료 |

기능 키와 Ctrl+L, Ctrl+Q는 입력창보다 우선합니다.

## 명령

자연어는 해석하지 않습니다. 잘못된 명령은 앱을 종료하지 않고 예시와 함께 오류를 보여 줍니다.

```text
/help
/project list
/project select demo-api
/project select demo-web
/test
/jobs
/cancel job-0001
/review
/lab
/history
/quiet on
/quiet off
```

기본 선택은 `demo-api`입니다. `/test`는 가상 FAIL 시나리오를 재생하고 오류 사례를 만듭니다. 기본 지연은 5초라서, 그 전에 취소 버튼이나 `/cancel job-0001`을 사용할 수 있습니다. PASS를 보려면 `demo-web`을 선택한 뒤 `/test`를 실행합니다.

Review에서 라벨을 승인, 수정, 보류할 수 있습니다. 예측 초안은 `RULE_BASED`로 표시되고, 확정 라벨은 승인 또는 수정 뒤에만 기록됩니다. 승인이나 수정 뒤에만 해결 원인과 방법을 저장합니다. 보류는 확정 건수에서 빠집니다. 라벨을 바꿔도 학습은 시작하지 않습니다. 기본 모델이 있으면 다음 실패 로그의 초안은 `MODEL`이고, 없으면 `RULE_BASED`입니다. 초안이 도착하기 전에는 라벨과 점수가 없습니다.

DEMO Lab은 학습하지 않습니다. 화면에 `DEMO에서는 학습하지 않습니다`라고 표시하고 버튼을 끄며, 평가 점수를 만들지 않습니다. LIVE Lab은 확정 건수, 클래스 분포, 분할 미리보기를 보여 줍니다. 조건이 부족하면 그 이유를 표시하고 학습 행을 만들지 않습니다. 학습이 끝나면 macro F1, 클래스별 점수, 혼동행렬을 규칙 baseline과 함께 보여 줍니다. 기본 모델은 사용자가 비교 뒤에 고릅니다.

History의 검색은 키워드 부분 일치입니다. 가상 예시는 `FIXTURE`, 이번 실행에서 저장한 기록은 `SESSION`입니다.

## 안전 경계

- 사용자 입력을 셸로 실행하지 않습니다. 워커는 등록된 `{python}` argv만 실행합니다.
- 로그와 프로젝트 내용을 외부 LLM으로 보내지 않습니다.
- LIVE 모드라고 해서 워커 없이 성공한 작업을 만들지 않습니다.
- 학습 문장 벡터와 유사 검색은 다운로드가 없는 `hashing-char-ngram-v1`입니다. 유료 임베딩 API는 없습니다.
- 학습이 끝나도 기본 모델을 자동으로 바꾸지 않습니다. 임대가 끊긴 학습은 다시 큐에 넣지 않습니다.

## 알려진 제한

- DEMO 세션 데이터는 종료 시 사라집니다. LIVE의 프로젝트 등록, 작업 등록, 실패 로그 가져오기, 작업, 검토는 PostgreSQL에 남습니다.
- DEMO 취소는 프로세스가 없으므로 요청과 종료 확인이 한 단계에서 끝납니다. LIVE 취소는 프로세스 종료를 확인한 뒤에만 `CANCELLED`가 됩니다.
- 캐릭터는 학습 실행이 `RUNNING`일 때만 TRAINING이고, 기본이 아닌 최신 모델이 있을 때 REPORTING입니다. 라벨 승인만으로는 그 상태로 바뀌지 않습니다.
- 기본 모델이 있으면 새 실패 로그 초안은 `MODEL`이고, 응답 전에는 `PENDING`입니다. 기본 모델이 없거나 파일·응답이 실패하면 `RULE_BASED`로 닫고 다시 추론하지 않습니다. 미검토 초안은 확정 라벨이 아닙니다.
- 비슷한 실패는 확정 기록의 로컬 해시 코사인으로 찾고, 답변은 그 기록만 인용합니다. 유사도는 정답 확률이 아닙니다. 외부 LLM은 없습니다. 단계 라벨이 없어 단계 예측은 하지 않습니다.
- softmax 출력은 보정된 정답 확률이 아닙니다. 점수는 테스트 분할에서 센 값입니다.
- 2026-11-10에 Docker CLI와 Compose 설정 검사는 통과했습니다. 데몬 파이프 `dockerDesktopLinuxEngine`이 없어 Compose `up`과 health 폴링은 실행하지 않았습니다. Linux용 `scripts/*.sh`와 CUDA 학습도 실행하지 않았습니다.

## 문서

- [프로젝트](docs/PROJECT.md)
- [아키텍처](docs/ARCHITECTURE.md)
- [API 초안](docs/API.md)
- [데이터 모델](docs/DATA_MODEL.md)
- [보안](docs/SECURITY.md)
- [UI](docs/UI_SPEC.md)
- [로드맵](docs/ROADMAP.md)
- [테스트 계획](docs/TEST_PLAN.md)
