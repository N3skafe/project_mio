# 아키텍처

작업 디렉터리가 저장소 루트다. 요청서의 `maidops-lab/` 트리는 제품 이름이지, 한 단계 더 들어간 폴더가 아니다. 그래서 README와 `tui/`를 이 디렉터리에 두었다.

## PHASE 1에서 실행되는 것

```text
명령 입력
  -> commands/parser.py
  -> commands/executor.py
  -> LabService
       DemoService            모드가 DEMO일 때
       UnavailableLiveService 모드가 LIVE일 때
  -> 화면 위젯이 스냅샷을 다시 그린다
```

UI는 서비스를 호출할 뿐 작업 상태를 직접 성공으로 바꾸지 않는다. 캐릭터 상태는 `characters/state.py`가 연결 상태, 작업, 오류 사례로 계산한다.

네 업무 화면은 별도 `Screen`으로 바꾸지 않는다. 한 화면의 `ContentSwitcher` 안에서 Workspace, Review, Lab, History를 바꾼다. 캐릭터 패널과 명령창과 활동 로그는 그대로라서, 상태 갱신이 로그를 지우거나 입력 포커스를 가져가지 않는다. 도움말만 모달 `Screen`이다. 뷰 파일은 `tui/src/maidops_tui/screens/`에 있다.

## 서비스 계약

`services/protocol.py`의 `LabService`가 프로젝트 조회, 작업 생성과 취소, 출력, 오류 사례, 라벨 검토, 해결 기록, 키워드 검색을 정의한다. PHASE 2의 `ApiService`는 이 계약을 구현하고 HTTP를 호출한다. PHASE 1에는 그 클래스가 없다.

LIVE는 `UnavailableLiveService`다. 소켓을 열지 않고 `LiveModeUnavailable`을 던진다. 빈 목록을 성공처럼 반환하지 않는다.

## 가상 작업의 완료와 취소

`DemoService`는 작업마다 토큰을 둔다. 완료 코루틴은 `asyncio.sleep` 뒤에 잠금을 잡고, 토큰이 같고 상태가 `RUNNING`일 때만 PASS 또는 FAIL을 기록한다.

취소는 같은 잠금에서 토큰을 올리고 `cancel_requested_at`을 남긴 다음 상태를 `CANCELLED`로 닫는다. PHASE 1에는 프로세스가 없어서 요청과 종료 확인이 한 단계다. 출력에는 `CANCEL requested`와 `RESULT CANCELLED`가 함께 남는다. 잠금을 놓기 전에 토큰이 바뀌므로, 이미 잠금을 기다리는 늦은 완료도 성공으로 덮어쓰지 못한다.

작업 딕셔너리의 키는 작업 id다. 한 작업의 상태 전이는 다른 작업 객체를 교체하지 않는다.

## 화면이 구분하는 데이터

- 실패 라벨의 예측 초안은 `source=RULE_BASED`이고 규칙 버전은 `rules-1`이다. 모델 추론이 아니다.
- `confirmed_label`은 승인 또는 수정된 사례에만 있다. 초안과 보류는 빠진다.
- 사용자의 승인, 수정, 보류는 `source=USER`인 이력으로 남는다.
- 처음부터 들어 있는 해결 기록은 `origin=FIXTURE`다.
- 이번 프로세스에서 저장한 해결 기록은 `origin=SESSION`이다.
- DEMO Lab은 세션의 확정 건수를 보여 주고 학습하지 않는다. 점수는 보여 주지 않는다. LIVE Lab은 연구실 상태와 끝난 모델의 평가를 보여 준다.

TUI 색은 Textual 기본 테마 변수인 `$panel`을 덮어쓰지 않는다. `hatch` 규칙이 그 이름을 색 값으로 바꾸면 스타일 파싱이 깨지기 때문이다. 앱 전용 색은 `$maid-` 접두사를 쓴다.

## PHASE 2에서 실행되는 것

DEMO는 이전과 같이 메모리의 `DemoService`입니다. LIVE는 `ApiService`가 HTTP로 백엔드를 호출합니다.

```text
TUI LIVE
  -> ApiService (httpx)
  -> GET /api/v1/health
  -> Spring Boot 3.5.16
  -> PostgreSQL
```

연결 실패, 시간 초과, 데이터베이스 DOWN은 `DISCONNECTED`와 한국어 오류로 남고 작업을 만들지 않습니다. health가 UP이어도 `worker`는 `NOT_CONNECTED`입니다. `POST /api/v1/jobs`는 `QUEUED`만 만들고 `started_at`을 비웁니다. 성공으로 끝내는 HTTP API는 없습니다.

같은 `Idempotency-Key`와 같은 본문은 같은 작업을 반환합니다. 같은 키와 다른 본문은 409입니다. 종료된 작업은 취소할 수 없습니다. `applyTerminalResultIfRunning`은 RUNNING일 때만 종료 상태를 쓰고, HTTP에 연결되어 있지 않습니다. QUEUED나 CANCELLED에는 늦은 성공을 덮어쓰지 않습니다.

## 워커와 라벨

`worker/`는 등록된 `{python}` argv만 `shell=False`로 실행합니다. 실패 로그의 라벨 초안은 워커가 고르지 않고, API의 `FailureRuleClassifier`가 키워드로 만듭니다. TUI DEMO도 같은 목록을 `rules.py`로 적용합니다. 기본 모델이 있으면 새 초안은 `MODEL`이고, 없으면 `RULE_BASED`입니다. 서버는 체크포인트를 실행하지 않고, 학습기가 argmax만 반환합니다. 외부 LLM과 임베딩 검색은 없습니다.

## 학습

```text
TUI LIVE Lab
  -> POST /api/v1/training-runs
  -> PostgreSQL QUEUED
  -> trainer/ claim
  -> hashing-char-ngram-v1 + PyTorch MLP
  -> 모델 파일과 혼동행렬
  -> API가 점수를 다시 계산하고 SUCCEEDED
  -> 사용자는 비교 뒤에 select-default
```

Java가 자격, 그룹 분할, 앵커, 저장, 체크섬, 지표 일치를 담당합니다. Python이 임베딩, MLP, 테스트 평가, 규칙 baseline, 파일 쓰기를 담당합니다. 테스트 분할은 한 번만 평가합니다. 예측은 argmax입니다. softmax는 보정된 확률이 아닙니다.

장치는 `cpu`, `cuda`, `auto`입니다. 환경 변수 `MAIDOPS_TRAIN_DEVICE`의 기본값은 `auto`입니다. `cuda`를 지정했는데 CUDA가 없으면 CPU로 바꾸지 않고 실패합니다. 모델 디렉터리는 `MAIDOPS_MODEL_DIR`이고 기본값은 `data/models`입니다. 백엔드와 학습기가 같은 디렉터리를 봐야 합니다.

## 선택한 이후 단계 버전

PHASE 1 의존성 위에 백엔드를 올렸습니다.

- Java 21. 이 세션의 백엔드 테스트 런타임은 Temurin 21.0.12.1입니다. 기본 `JAVA_HOME`은 JDK 11이고 `C:\Program Files\Java\jdk-21`은 이 PC에 없습니다. 빌드 전에 JDK 21을 `JAVA_HOME`으로 지정합니다.
- Spring Boot 3.5.16. 2026-06-25 릴리스이며 Java 17 이상이라 Java 21과 맞습니다. 근거는 [v3.5.16 릴리스](https://github.com/spring-projects/spring-boot/releases/tag/v3.5.16)입니다. Spring Boot 4.1.1도 Java 21을 지원하지만 Spring Framework 7 전환이 포함되므로 3.5 선을 유지합니다.

- Python 3.11. 개발 머신에서 `py -3.11`은 3.11.9였다.
- Textual 8.2.8. 2026-10-06에 PyPI 안정 최신으로 확인했고, 설치본의 `App.run_test`, `Binding.priority`, `RichLog.write`, `ContentSwitcher`, `HORIZONTAL_BREAKPOINTS`를 확인한 뒤 사용했다.
- pytest 9.1.1, pytest-asyncio 1.4.0.
- HTTP 클라이언트는 `httpx==0.28.1`이다.
- PostgreSQL 16 이미지와 Compose 파일은 `infra/docker-compose.yml`에 있다. 백엔드 테스트는 내장 PostgreSQL을 사용한다. 이 개발 PC에는 Docker가 없어 Compose 기동은 확인하지 못했다.
- PyTorch 2.14.1 CPU 휠. 설치 인덱스는 `https://download.pytorch.org/whl/cpu`입니다. 이 PC에서는 `torch 2.14.1+cpu`가 설치되었고 `cuda.is_available()`은 거짓입니다. CUDA 학습 실행은 확인하지 않았습니다.

Redis, Kafka, Kubernetes, 다중 에이전트는 초기 범위 밖이다.
