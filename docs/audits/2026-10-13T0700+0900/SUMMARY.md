# MaidOps Lab 감사 요약

감사 시각: 2026-10-13 06:45–07:00 (KST)  
대상 commit: `ab1d66090e296f3a73aef14dad59130eae2cc34d` (`main`, `origin/main`, 메시지 `first commit for project mio`)  
시작 시 작업 트리: 깨끗함. 제품 코드는 수정하지 않았다.

## 한 줄 결론

PHASE 1~5의 구현과 기존 자동 테스트는 상당 부분 문서의 상태 기계와 맞다. 다만 워커 예외 시 프로세스가 남고, macro F1은 예측하지 않은 클래스를 평균에서 빼며, 일부 문서는 실제 모델 초안 동작과 다르다. 사용자 DB를 피했기 때문에 PostgreSQL 16 위의 전체 LIVE 시연은 끝내지 못했다.

## 실행 환경

| 항목 | 확인 값 |
| --- | --- |
| OS | Windows NT 10.0.26200 |
| Python | 3.11.9 (`py -3.11`, `F:\python311\python.exe`) |
| TUI venv | Textual 8.2.8, pytest 9.1.1, httpx 0.28.1 |
| Trainer venv | torch 2.14.1+cpu, `cuda.is_available()` 거짓. NumPy 없음(경고만, 테스트는 통과) |
| Worker venv | 실행 불가. `pyvenv.cfg`의 기준 인터프리터 `C:\Program Files\Python311\python.exe`가 없다 |
| Java | PATH의 `java`/`javac`는 21.0.12.1. 사용자 `JAVA_HOME`은 `C:\dev\jdk-11.0.0.1` |
| 문서의 JDK 경로 | `C:\Program Files\Java\jdk-21` 없음. 실제 디렉터리는 `C:\Program Files\Java\jdk-21.0.12.1` |
| Docker | Server 29.8.2, Compose v5.6.0 |
| 이미 떠 있는 스택 | `infra-postgres-1`, `infra-backend-1`, `infra-worker-1`, `infra-trainer-1`. 호스트 포트 `127.0.0.1:5432`, `127.0.0.1:8080` |
| 그 스택의 health (GET 1회) | `status=UP`, `database=UP`, `worker=CONNECTED`, `authentication=NONE` |
| psql 클라이언트 | 없음 |

이미 떠 있는 `maidops` 데이터베이스에는 접속하지 않았다. 백엔드 테스트는 Zonky 내장 PostgreSQL 14.10, `127.0.0.1:4039`, 데이터베이스 이름 `postgres`만 사용했다. 테스트 JVM 종료 후 4039는 열려 있지 않다. 감사 중 셸에 잠시 넣은 JDK 21 경로는 원래 `JAVA_HOME`과 PATH로 되돌렸다.

## Phase별 결과

| Phase | 정적 검토 | 실행 검증 | 통합 검증 | BLOCKED |
| --- | --- | --- | --- | --- |
| 1 TUI·DEMO | 화면·명령·DEMO 학습 금지는 코드와 단위 테스트가 맞음 | TUI pytest 59개 중 앱 테스트가 간헐 실패. 서비스 테스트는 통과 | headless Textual. 실제 터미널 목시 확인은 하지 않음 | 한글·레이아웃의 사람 눈 확인 |
| 2 API·DB | 계약, idempotency 잠금, 바인딩, 인증 없음이 문서와 맞음 | 내장 PG 14.10에서 백엔드 27개 통과. Flyway V1–V6가 빈 DB에 적용되고 재실행은 no-op | 사용자 PG 16에는 쓰지 않음. 기동 중인 API는 health만 읽음 | 빈 PostgreSQL 16에 대한 마이그레이션 실행 |
| 3 워커 | 등록 argv, `shell=False`, claim의 `SKIP LOCKED`, 임대 만료 후 종료 행 보호 | fixture 실행 4개 통과. symlink 거부·일반 자식 종료는 감사 테스트 통과. 상태 조회 예외 시 프로세스 잔존은 재현 | 실행 중인 Docker 워커에 작업을 넣지 않음 | 사용자 스택에서의 취소·단절·재시작 |
| 4 라벨·검색 | 다섯 라벨, 미확정 초안, 키워드 검색, 외부 LLM 없음 | 규칙 테스트와 API 통합 테스트 통과. URI 비밀번호는 마스킹되지 않음 | 검토 충돌의 병렬 HTTP는 실행하지 않음 | 사용자 DB의 검색·검토 데이터 |
| 5 학습·평가 | 확정 라벨 snapshot, 그룹 분할, 기본 모델 자동 교체 없음, 해시 임베딩 | CPU 소형 fixture 학습 7개 통과. macro F1 정의 문제는 재현. CUDA 없음 | API 학습 테스트는 더미 파일과 미리 만든 행렬. 실제 가중치 재평가가 아님 | CUDA, 실데이터 일반화, LIVE 학습 왕복 |

## 심각도별 문제 수

| 심각도 | 수 | ID |
| --- | --- | --- |
| CRITICAL | 0 | |
| HIGH | 1 | F-01 |
| MEDIUM | 8 | F-02, F-03, F-04, F-05, F-06, F-07, F-08, F-09 |
| LOW | 3 | F-10, F-11, F-12 |

## 실행하지 못한 항목

- 빈 PostgreSQL 16에서의 마이그레이션과 재실행. 5432는 이미 사용 중인 개발 DB다.
- TUI LIVE와 워커·학습기를 이어서 하는 17단계 통합. 같은 이유로 사용자 DB에 작업을 만들지 않았다.
- 실제 터미널에서 한글, ASCII 캐릭터, 색, 작은 창을 눈으로 확인.
- CUDA 학습. 설치된 휠은 CPU이고 `cuda.is_available()`은 거짓이다.
- 장시간 학습, 모델 다운로드, 외부 LLM. 설계상 다운로드와 외부 LLM은 없고, 이번 감사도 호출하지 않았다.
- JDK 11로 `mvnw`를 일부러 실패시키는 실행. 경로 불일치는 확인했고, 테스트는 JDK 21.0.12.1로만 실행했다.

## 시연 가능 여부

DEMO는 `tui/.venv`로 문서의 pytest와 같은 인터프리터에서 실행할 수 있다. Java·DB·GPU 없이 서비스 테스트가 통과했다. Textual 앱 테스트는 같은 환경에서 가끔 실패하므로, 한 번의 녹색 결과를 화면 품질의 증거로 쓰지 않는 것이 맞다. 사람 눈의 터미널 확인은 아직이다.

LIVE 스택은 이 PC에서 이미 `127.0.0.1`에 떠 있고 health는 UP이다. 그 스택에 감사 작업을 넣지 않았으므로, 지금 화면으로 학습까지 가는 시연이 된다고 말하지 않는다.

## 안전한 로컬 사용 가능 여부

localhost 바인딩과 인증 없음은 문서와 같다. 호스트 포트는 `127.0.0.1`에만 열려 있다. 그 상태에서 외부 전송이나 유료 API 호출은 코드에서 찾지 못했다.

그대로 안전하다고 말하지 않는 이유:

- 워커가 작업 상태 조회에서 예외를 만나면 자식 프로세스가 남고, 그 순간 타임아웃 루프도 끝난다.
- 연결 URI 안의 비밀번호는 로그 마스킹을 통과한다.
- 출력량 제한으로 잘린 뒤에도 종료 코드 0이면 성공 finish로 올라갈 수 있고, 잘림 플래그는 finish 본문에 없다.

## 우선 조치

1. F-01. 상태 조회·heartbeat 예외가 나도 프로세스 트리를 끝내고, 그 다음에 실패를 기록한다.
2. F-02. 지원이 있는 클래스의 F1을 0으로 두고 macro 평균에 포함한다. 화면 문구도 그 정의와 같게 한다.
3. F-03, F-04. URI 비밀과 출력 잘림을 성공 로그로 남기지 않는다.
4. F-05, F-06. README·PROJECT·SECURITY·`test-backend.ps1`의 JDK 경로를 현재 구현과 이 PC의 JDK 21 경로에 맞춘다.
5. 전체 LIVE 확인이 필요하면, 아래 격리 실행을 승인한 뒤에 한다. 기존 5432/8080 스택은 중지하지 않는다.

격리 실행 계획 (아직 실행하지 않음):

- 새 Compose 프로젝트 이름과 호스트 포트 `127.0.0.1:55432`, `127.0.0.1:18080`만 사용한다.
- 데이터 볼륨은 감사 전용 새 볼륨이다. 기존 `maidops-models`와 5432 데이터는 재사용하지 않는다.
- 이미지 `postgres:16-alpine`과 현재 빌드 캐시만 사용한다. 추가 pull이 필요하면 그 시점에 다시 알린다.
- 작업 명령은 `fixtures/trusted-projects`의 등록 argv만 실행한다.
