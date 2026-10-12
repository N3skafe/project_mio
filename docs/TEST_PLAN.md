# 테스트 계획

PHASE 1 테스트는 `tui/tests`에 있다. `cd tui` 후 `.venv`의 pytest로 실행한다. 이 문서의 항목은 그 테스트가 다루는 범위다. 특정 실행의 통과 여부는 테스트 리포트로만 말한다.

## 명령

- 문서에 적힌 명령 예시가 파싱된다.
- 자연어, 알 수 없는 명령, 빠진 인자, 남은 인자는 오류와 예시를 만든다.
- 오류 명령은 앱을 종료하지 않는다.
- 조용한 모드 on/off가 파싱된다.

## 서비스

- `demo-api` 실패와 `demo-web` 성공이 서로의 상태와 출력을 덮어쓰지 않는다.
- 취소 뒤 이전 토큰과 새 토큰의 완료 처리가 PASS / FAIL을 쓰지 않는다. 지연이 끝난 뒤에도 `CANCELLED`가 유지된다.
- 실패 초안은 `RULE_BASED`이고 규칙 버전은 `rules-1`이다. 가상 해결 기록의 origin은 `FIXTURE`다.
- 미검토 초안과 보류의 확정 라벨은 없다. 수정 뒤에는 예측 초안과 확정 라벨이 다를 수 있다.
- 같은 라벨로의 수정은 거부된다. 다른 라벨로의 수정, 보류, 승인이 이력에 남는다.
- 보류는 확정 건수에서 빠지고, 승인 또는 수정만 들어간다.
- 초안이나 보류에는 해결 기록을 저장하지 않는다.
- 새 `DemoService`는 이전 세션의 작업과 검토를 갖지 않는다. fixture 해결 기록만 다시 보인다.
- 키워드가 없으면 빈 결과다. 빈 검색어는 오류다.
- 출력 한도를 넘으면 `[출력 잘림]`이 붙고 `output_truncated`가 참이다.
- 종료된 작업은 다시 취소할 수 없다.
- LIVE 서비스는 작업을 만들지 않고 네트워크를 열지 않았다는 오류를 반환한다.

## 캐릭터

- 상태마다 표정과 대사가 다르다.
- 실패 대사에 성공이나 학습 완료가 없다.
- 실행 중이면 WORKING, 초안이면 NEEDS_REVIEW, 검토가 끝난 실패면 FAILED다.
- PHASE 1 파생은 TRAINING과 REPORTING을 반환하지 않는다.
- DISCONNECTED가 다른 상태보다 우선한다.

## TUI

- F2부터 F5까지 화면이 바뀌고, 입력창에 포커스가 있어도 동작한다.
- Ctrl+L이 명령창으로 온다.
- F1 도움말에 명령이 있고 Escape로 닫힌다.
- 조용한 모드는 대사만 숨긴다. DEMO 표시와 상태는 남는다.
- `/test` 후 로그에 `RESULT FAIL`이 보이고 캐릭터가 NEEDS_REVIEW가 된다.
- 승인 뒤 활동 로그는 학습을 시작하지 않았다고 말하고, 캐릭터는 TRAINING이 아니다.
- Lab 버튼은 비활성화되고 평가 점수가 없다. 확정 건수는 실제 승인 수다.
- `/cancel` 결과가 PASS나 FAIL로 바뀌지 않는다.
- History에서 `5432` 검색은 FIXTURE라고 표시한다.
- 조용한 모드로 캐릭터를 바꿔도 작업 로그와 명령 포커스가 유지된다.
- 앱을 새로 만들면 이전 세션 사례가 없다.
- 78x24에서도 도움말과 비활성 Lab 버튼에 접근할 수 있다.
- LIVE 화면은 DISCONNECTED이며 `/test`가 성공을 가장하지 않는다.

## PHASE 2

백엔드 테스트는 `backend`에서 `mvnw.cmd -B test`로 실행합니다. JDK 21이 필요합니다. 내장 PostgreSQL을 사용하며 Docker Compose 기동 테스트는 이 환경에서 실행하지 않습니다.

- `POST /api/v1/jobs`는 QUEUED이고 `started_at`이 비어 있으며 RESULT PASS/FAIL 이벤트가 없습니다.
- 같은 Idempotency-Key와 같은 본문은 같은 작업을 반환합니다. 다른 본문은 409입니다.
- 입력 누락, 없는 프로젝트, limit 0, 빈 검색어, 잘못된 cursor는 표준 오류 본문입니다.
- QUEUED 취소는 CANCELLED이고, 그 뒤의 완료 처리는 상태를 바꾸지 않습니다.
- RUNNING으로 둔 작업에 취소와 완료가 겹치면 하나의 종료 상태만 남습니다.
- 성공으로 바꾸는 HTTP 경로는 404입니다.
- 목록 페이지에 중복이 없습니다.
- 초안 해결 기록 저장은 거부되고, 수정 뒤에만 SESSION 해결 기록이 검색됩니다.
- `/api/v1/health`는 database UP, worker NOT_CONNECTED입니다.

TUI의 LIVE 테스트는 닫힌 포트와 MockTransport로 연결 실패와 QUEUED 유지 를 확인합니다. DEMO 테스트는 이전과 같이 통과해야 합니다.

## PHASE 4

- 규칙 분류는 다섯 라벨과 우선순위를 맞추고, 숫자 안에 들어간 401/403은 맞추지 않습니다. 점수 필드는 없습니다.
- `boom` 로그는 `OTHER`, `RULE_BASED`, `confirmed_label` null입니다.
- PostgreSQL 연결 로그의 초안은 `DB_CONNECTION`이며 보류 뒤에는 확정 목록에 없습니다.
- 입력 검증 로그를 다른 라벨로 수정하면 `draft_label`은 남고 `confirmed_label`만 바뀝니다. 이력의 첫 행은 `RULE_BASED`, 다음 행은 `USER`입니다.
- 원인 키워드 검색은 `RESOLUTION`을 반환합니다. 없는 검색어는 빈 목록입니다.

## PHASE 5

백엔드 테스트는 `TrainingLabIntegrationTest`, `DatasetSplitterTest`, `ClassificationMetricsTest`입니다. 학습기 테스트는 `trainer`에서 pytest로 실행합니다. DEMO Lab 테스트는 이전과 같이 점수 없이 버튼이 꺼져 있어야 합니다.

- 확정 사례가 부족하면 409이고 학습 행과 점수가 없습니다. 초안과 보류는 건수에 넣지 않습니다.
- 같은 작업이나 같은 정규화 템플릿은 한 분할에만 있습니다. 이후 실행에서 기존 TEST 템플릿은 TRAIN으로 옮기지 않습니다.
- 손계산 혼동행렬의 macro F1은 47/60입니다. 지원이 0인 클래스의 F1은 null입니다.
- 학습이 끝나도 `is_default`는 거짓입니다. 선택 뒤에만 참이고, 다음 모델이 그 기본값을 바꾸지 않습니다.
- 임대가 끊기면 `FAILED`이고 다시 claim되지 않으며 모델 파일이 없습니다.
- CPU에서 분리 가능한 토큰 데이터를 학습하면 테스트 macro F1이 규칙 baseline보다 큽니다. 그룹이 두 분할에 있으면 파일을 쓰지 않습니다.
- CUDA가 없을 때 `cuda` 요청은 예외이고 `auto`는 CPU입니다.
- 형식 다른 파일은 체크포인트로 열지 않습니다.
- 캐릭터는 학습 `RUNNING`일 때 TRAINING이고, 기본이 아닌 최신 모델이 있을 때 REPORTING입니다. 라벨 승인만으로는 TRAINING이 아닙니다.
- 기본 모델이 없으면 실패 초안은 `RULE_BASED`입니다. 기본 모델과 파일이 있으면 라벨은 비어 있고 승인할 수 없습니다. 학습기가 라벨을 반환하면 `MODEL`이고 확정 라벨은 여전히 없습니다. 임대가 끊기면 `RULE_BASED`로 닫고 다시 claim되지 않습니다.

임베딩 의미 검색, 근거 있는 답변 생성, 새 로그에 대한 모델 추론, CUDA 위에서의 실제 학습, Docker Compose 기동은 이 환경에서 실행하지 않습니다. Linux 실행도 확인하지 않습니다.
