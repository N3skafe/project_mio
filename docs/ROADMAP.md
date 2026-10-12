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
| 임베딩 의미 검색 | PHASE 4의 별도 요청 | 미구현 |
| 근거 있는 답변 생성 | PHASE 4의 별도 요청 | 미구현 |
| 문장 임베딩과 작은 MLP 학습 | PHASE 5 | 완료. 고정 해시 `hashing-char-ngram-v1`과 PyTorch MLP. 다운로드 없음 |
| 모델 버전 비교와 기본 모델 선택 | PHASE 5 | 완료. 학습 후 자동 교체 없음. 사용자가 기본 모델을 고름 |
| 새 로그에 학습 모델 적용 | PHASE 5 이후 | 완료. 기본 모델이 있으면 초안은 `MODEL`. 없으면 `RULE_BASED`. 미검토 초안은 확정이 아님 |
| Redis, Kafka, Kubernetes, 다중 에이전트 | 초기 범위 밖 | 미구현 |

PHASE 2를 시작할 때 Spring Boot 3.5.16과 Java 21을 기준으로 한다. 이유는 `docs/ARCHITECTURE.md`에 있다.
