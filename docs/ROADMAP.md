# 로드맵

상태는 이 저장소 기준으로 완료, 진행, 미구현 중 하나다.

| 기능 | 단계 | 상태 |
| --- | --- | --- |
| Textual 앱, 캐릭터, 네 화면, 명령 | PHASE 1 | 완료 |
| DEMO 가상 PASS / FAIL / 취소 | PHASE 1 | 완료 |
| 라벨 승인, 수정, 보류와 세션 검색 | PHASE 1 | 완료 |
| 조용한 모드와 도움말 | PHASE 1 | 완료 |
| Lab 학습과 평가 | PHASE 5 | 완료. DEMO는 학습하지 않음. LIVE는 조건 충족 시에만 학습 |
| Spring Boot API | PHASE 2 | 완료 |
| PostgreSQL과 마이그레이션 | PHASE 2 | 완료 |
| TUI ApiService | PHASE 2 | 완료 |
| 실행 워커 없이 QUEUED 유지 | PHASE 2 | 완료 |
| 인증 | PHASE 2 이후의 다중 사용자 | 미구현. 초기에는 localhost 단일 사용자이며 인증 없음을 명시 |
| 등록 명령 실행 워커 | PHASE 3 | 완료 |
| 취소와 프로세스 트리 종료 확인의 분리 | PHASE 3 | 완료 |
| 워커 손실 시 자동 재실행 금지 | PHASE 3 | 완료 |
| 규칙 기반 라벨 초안 | PHASE 4 | 완료. source=RULE_BASED, 규칙 버전 rules-1. 미검토 초안은 확정 라벨이 아님 |
| 키워드 검색 | PHASE 1의 세션 검색, PHASE 4에서 원인·해결과 오류 원문 | 완료 |
| 임베딩 의미 검색 | PHASE 7 | 완료. 확정 기록만 `hashing-char-ngram-v1` 코사인. 키워드 검색은 유지. 외부 API 없음 |
| 근거 있는 답변 생성 | PHASE 7 | 완료. 찾은 기록만 인용. 없으면 없다고 말한다 |
| 문장 임베딩과 작은 MLP 학습 | PHASE 5 | 완료. 고정 해시 `hashing-char-ngram-v1`과 PyTorch MLP. 다운로드 없음 |
| 모델 버전 비교와 기본 모델 선택 | PHASE 5 | 완료. 학습 후 자동 교체 없음. 사용자가 기본 모델을 고름 |
| 새 로그에 학습 모델 적용 | PHASE 5 이후 | 완료. 기본 모델이 있으면 초안은 `MODEL`. 없으면 `RULE_BASED`. 미검토 초안은 확정이 아님 |
| 사용자 프로젝트·작업 등록과 실패 로그 가져오기 | PHASE 6 | 완료. LIVE만. `{python}`과 workspace 안 경로만 등록. 가져오기는 작업을 만들지 않음 |
| 초안 근거, 유사 요약, 라벨 점검 목록 | PHASE 8 | 완료. 자신 hit 제외. 체크리스트는 조언이며 학습 점수가 아님 |
| LIVE 원클릭 기동, 사전 점검, health의 worker/trainer 구분 | PHASE 9 | 완료. Compose 풀스택은 heartbeat로 CONNECTED. 백엔드만 켜면 NOT_CONNECTED. DEMO는 Docker 불필요 |
| 워커 감독 실패 정리, 출력 한도 실패, 로그 마스킹, macro F1 일치 | PHASE 10 | 완료. 상태·하트비트·출력 예외는 프로세스 트리를 끝내고 성공으로 닫지 않음 |
| 검토 revision 충돌 방지 | PHASE 10 | 완료. `expected_revision`이 최신 개정과 다르면 409. 갱신은 행 잠금 |
| 학습 complete 체크포인트 형식 가드 | PHASE 10 | 완료. 서버는 PyTorch를 실행하지 않고 format·embedding·label schema 문자열이 없으면 거절 |
| 실행 중 로그 배치 전송 | PHASE 10 | 완료. 미확인 배치는 워커가 죽으면 남지 않음. 작업은 다시 큐에 넣지 않음 |
| Redis, Kafka, Kubernetes, 다중 에이전트 | 초기 범위 밖 | 미구현 |

백엔드는 Spring Boot 4.1.2와 Java 21을 사용한다. 3.5.x OSS 지원이 끝나 IDE 경고를 피하려고 4.1.2로 올렸다. 이유는 `docs/ARCHITECTURE.md`에 있다.
